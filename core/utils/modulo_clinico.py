import openai
import re
import time
import unicodedata
import string
from typing import Dict, Any
from datetime import datetime
from datetime import datetime, timedelta  # ← añadimos timedelta para cálculos de reingreso


from core.utils.clinico_contexto import hay_contexto_clinico_anterior
from core.utils_contacto import obtener_mensaje_contacto
from core.funciones_asistente import detectar_emociones_negativas
from core.utils.generador_openai import generar_respuesta_con_openai
from core.constantes import CLINICO, CLINICO_CONTINUACION


from core.db.registro import (
    registrar_respuesta_openai,
    registrar_auditoria_respuesta,
    registrar_interaccion,
    registrar_emocion,
    registrar_emocion_clinica,
    registrar_historial_clinico,   # <- importante
)


from core.db.registro import registrar_historial_clinico

from core.db.sintomas import (
    registrar_sintoma,
    obtener_sintomas_existentes
)

from core.db.consulta import (
    obtener_emociones_ya_registradas,
    obtener_historial_clinico_usuario
)

from core.db.conexion import ejecutar_consulta  # Eliminado user_sessions

# Producción: considerar reingreso a partir de 60 segundos
REINGRESO_SEGUNDOS = 60

def armar_prompt_openai(historial_emociones, nuevas_emociones, ultima_interaccion, nombre_usuario=None):
    resumen = ""
    if historial_emociones:
        resumen += (
            f"El usuario {nombre_usuario or ''} ha consultado previamente por: "
            f"{', '.join(historial_emociones)}.\n"
        )
    if nuevas_emociones:
        resumen += (
            f"En esta interacción expresa: {', '.join(nuevas_emociones)}.\n"
        )
    if ultima_interaccion:
        resumen += f"Último comentario relevante del usuario: '{ultima_interaccion}'.\n"

    prompt = (
        "Sos un asistente clínico digital que acompaña a personas en situaciones emocionales delicadas. "
        "Analizá el siguiente contexto emocional, detectá patrones relevantes y sugerí con empatía posibles líneas de abordaje clínico, "
        "sin emitir diagnósticos tajantes ni frases genéricas.\n\n"
        f"{resumen}\n"
        "1. ¿Qué emociones/síntomas son predominantes en este usuario?\n"
        "2. ¿Cuál podría ser el cuadro o estado anímico principal? (Describilo con cautela, nunca de forma definitiva)\n"
        "3. Sugerí, de forma amable y profesional, si corresponde derivar al Lic. Daniel O. Bustamante, sin forzar la consulta.\n"
        "4. Sugerí en una línea, de modo orientativo y no definitivo, qué cuadro clínico podría estar predominando según la información, usando lenguaje comprensible para el usuario.\n"
        "Por favor, devolvé la respuesta en el siguiente formato JSON:\n"
        "{'emociones_predominantes': [], 'cuadro_clinico': '', 'mensaje_usuario': ''}"
    )
    return prompt




def armar_respuesta_usuario(respuesta_ia_json, emociones_actuales, nombre_usuario=None):
    texto_intro = ""
    if emociones_actuales:
        texto_intro = (
            f"Gracias por compartir lo que sentís. Hasta ahora mencionaste: {', '.join(emociones_actuales)}.\n"
        )
    mensaje_usuario = respuesta_ia_json.get("mensaje_usuario", "").strip()
    recomendacion = (
        "\nRecordá que este espacio no reemplaza la consulta con un profesional. "
        "Si lo deseás, podés escribirle al Lic. Daniel O. Bustamante para un acompañamiento más personalizado."
    )
    respuesta_final = f"{texto_intro}{mensaje_usuario}{recomendacion}"
    return respuesta_final




def normalizar_texto(texto: str) -> str:
    if not texto or not isinstance(texto, str):
        texto = ""
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("utf-8")
    texto = texto.translate(str.maketrans("", "", string.punctuation))
    return texto


def recuperar_historial_clinico(user_id, limite=5):
    query = """
    SELECT fecha, emociones, sintomas, tema, respuesta_openai, sugerencia, fase_evaluacion
    FROM historial_clinico_usuario
    WHERE user_id = %s AND eliminado = FALSE
    ORDER BY fecha DESC
    LIMIT %s
    """
    try:
        resultados = ejecutar_consulta(query, (user_id, limite))
        return resultados or []
    except Exception as e:
        print(f"🔴 Error al recuperar historial clínico: {e}")
        return []

def construir_resumen_historial(historial):
    """
    Construye un resumen seguro del historial clínico evitando KeyError.
    Soporta listas, tuplas y diccionarios.
    """
    temas = []
    for h in historial:
        # Si es lista o tupla y tiene al menos 4 elementos
        if isinstance(h, (list, tuple)) and len(h) > 3:
            if h[3]:
                temas.append(h[3])
        # Si es diccionario y contiene la clave 'tema'
        elif isinstance(h, dict) and "tema" in h:
            if h["tema"]:
                temas.append(h["tema"])

    return temas


# Diccionario de emociones clínicas observables
emociones_clinicas = {
    "angustia": ["angustiado", "angustia"],
    "ansiedad": ["ansioso", "ansiedad", "nervioso", "preocupado"],
    "estrés": ["estresado", "estrés"],
    "tristeza": ["triste", "deprimido", "bajoneado", "vacío"],
}

def detectar_emocion(texto: str) -> str | None:
    texto = texto.lower()
    for emocion, variantes in emociones_clinicas.items():
        for variante in variantes:
            if re.search(rf"\b{re.escape(variante)}\b", texto):
                return emocion
    return None

def procesar_clinico(input_data: Dict[str, Any]) -> Dict[str, Any]:
    mensaje_original = input_data["mensaje_original"]
    mensaje_usuario = normalizar_texto(input_data["mensaje_usuario"])
    user_id = input_data["user_id"]
    session = input_data["session"]
    contador = input_data["contador"]

    if contador == 1:
        historial_prev = recuperar_historial_clinico(user_id)
        if historial_prev:
            resumen = construir_resumen_historial(historial_prev)
            respuesta_historial = f"Bienvenido nuevamente. La última vez conversamos sobre {resumen}. ¿Querés que retomemos desde ahí?"
            session["ultimas_respuestas"].append(respuesta_historial)
            return {"respuesta": respuesta_historial, "session": session}

    sintomas_existentes = {normalizar_texto(s) for s in obtener_sintomas_existentes()}
    emociones_detectadas = detectar_emociones_negativas(mensaje_usuario) or []

    session.setdefault("emociones_detectadas", [])
    session.setdefault("emociones_totales_detectadas", 0)
    session.setdefault("emociones_sugerencia_realizada", False)
    session.setdefault("emociones_corte_aplicado", False)

    emociones_nuevas = []
    emociones_detectadas_normalizadas = [normalizar_texto(e) for e in emociones_detectadas]

    for emocion in emociones_detectadas_normalizadas:
        if emocion not in {normalizar_texto(e) for e in session["emociones_detectadas"]}:
            emociones_nuevas.append(emocion)

    # ==============================================================
    # 📌 Clasificación de emociones nuevas con OpenAI
    # ==============================================================
    
    for emocion in emociones_nuevas:
        prompt_cuadro = (
            f"A partir de la siguiente emoción detectada: '{emocion}', asigná un único cuadro clínico o patrón emocional.\n\n"
            "Tu tarea es analizar el síntoma y determinar el estado clínico más adecuado, basándote en criterios diagnósticos de la psicología o la psiquiatría. "
            "No respondas con explicaciones, sólo con el nombre del cuadro clínico más pertinente.\n"
            "Si la emoción no corresponde a ningún cuadro clínico definido, indicá únicamente: 'Patrón emocional que requiere evaluación profesional por el Lic. Daniel O. Bustamante'.\n\n"
            "Ejemplos válidos de cuadros clínicos:\n"
            "- Trastorno de ansiedad\n"
            "- Depresión mayor\n"
            "- Estrés postraumático\n"
            "- Trastorno de pánico\n"
            "- Baja autoestima\n"
            "- Estado confusional\n"
            "- Desgaste emocional\n"
            "- Trastorno de impulsividad\n"
            "- Insomnio crónico\n"
            "- Desorientación emocional\n"
            "- Sentimientos de aislamiento\n"
            "- Patrón emocional detectado\n\n"
            "Devolvé únicamente el nombre del cuadro clínico, sin explicaciones, ejemplos ni texto adicional."
        )
    
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt_cuadro}],
                max_tokens=50,
                temperature=0.0
            )
    
            cuadro_asignado = response.choices[0].message['content'].strip()
    
            # ✅ Si OpenAI no asigna nada, usar la frase profesional por defecto
            if not cuadro_asignado:
                cuadro_asignado = "Patrón emocional que requiere evaluación profesional por el Lic. Daniel O. Bustamante"
    
            registrar_sintoma(emocion, cuadro_asignado)
            print(f"🧠 OpenAI asignó el cuadro clínico: {cuadro_asignado} para la emoción '{emocion}'.")
    
        except Exception as e:
            print(f"❌ Error al obtener el cuadro clínico de OpenAI para '{emocion}': {e}")

    
    # Registrar historial clínico SIEMPRE que haya emociones detectadas
    if session["emociones_detectadas"]:
        respuesta_clinica = (
            "Gracias por compartir lo que estás atravesando. Si lo deseás, podés contactar al Lic. Bustamante por WhatsApp: +54 911 3310-1186."
        )
        interaccion_id = registrar_interaccion(user_id, mensaje_usuario, mensaje_original)
        registrar_respuesta_openai(interaccion_id, respuesta_clinica)
        registrar_historial_clinico(
            user_id=user_id,
            emociones=session.get("emociones_detectadas", []),
            sintomas=[],
            tema=None,
            respuesta_openai=respuesta_clinica,
            sugerencia="registro inmediato",
            fase_evaluacion=f"interacción {contador}",
            interaccion_id=interaccion_id,
            fecha=datetime.now(),
            fuente="web",
            origen="modulo_clinico",         # << estándar
            eliminado=False,
        )

        return {"respuesta": respuesta_clinica, "session": session}


    # Siempre registrar historial clínico desde la primera emoción detectada
    respuesta_clinica = (
        "Gracias por compartir lo que estás atravesando. Si lo deseás, podés contactar al Lic. Bustamante por WhatsApp: +54 911 3310-1186."
    )
    interaccion_id = registrar_interaccion(user_id, mensaje_usuario, mensaje_original)
    registrar_respuesta_openai(interaccion_id, respuesta_clinica)
    
    registrar_historial_clinico(
        user_id=user_id,
        emociones=session.get("emociones_detectadas", []),
        sintomas=[],
        tema=None,
        respuesta_openai=respuesta_clinica,
        sugerencia="registro inmediato",
        fase_evaluacion=f"interacción {contador}",
        interaccion_id=interaccion_id,
        fecha=datetime.now(),
        fuente="web",
        origen="modulo_clinico",
        eliminado=False,
    )

    
    return {"respuesta": respuesta_clinica, "session": session}


    for emocion in emociones_nuevas:
        prompt_cuadro = (
            f"A partir de la siguiente emoción detectada: '{emocion}', asigná un único cuadro clínico o patrón emocional.\n\n"
            "Tu tarea es analizar el síntoma y determinar el estado clínico más adecuado, basándote en criterios diagnósticos de la psicología o la psiquiatría. "
            "No respondas con explicaciones, sólo con el nombre del cuadro clínico más pertinente.\n\n"
            "Si la emoción no corresponde a ningún cuadro clínico definido, indicá únicamente: 'Patrón emocional detectado'.\n\n"
            "Ejemplos válidos de cuadros clínicos:\n"
            "- Trastorno de ansiedad\n"
            "- Depresión mayor\n"
            "- Estrés postraumático\n"
            "- Trastorno de pánico\n"
            "- Baja autoestima\n"
            "- Estado confusional\n"
            "- Desgaste emocional\n"
            "- Trastorno de impulsividad\n"
            "- Insomnio crónico\n"
            "- Desorientación emocional\n"
            "- Sentimientos de aislamiento\n"
            "- Patrón emocional detectado\n\n"
            "Devolvé únicamente el nombre del cuadro clínico, sin explicaciones, ejemplos ni texto adicional."
        )

        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt_cuadro}],
                max_tokens=50,
                temperature=0.0
            )
            cuadro_asignado = response.choices[0].message['content'].strip()
            if not cuadro_asignado:
                cuadro_asignado = "Patrón emocional detectado"

            registrar_sintoma(emocion, cuadro_asignado)
            print(f"🧠 OpenAI asignó el cuadro clínico: {cuadro_asignado} para la emoción '{emocion}'.")

        except Exception as e:
            print(f"❌ Error al obtener el cuadro clínico de OpenAI para '{emocion}': {e}")

    interaccion_id = registrar_interaccion(user_id, mensaje_usuario, mensaje_original)

    if session["emociones_totales_detectadas"] == 1:
        emocion = session["emociones_detectadas"][0]
        respuesta_original = (
            f"Por lo que mencionás, podría percibirse {emocion}. "
            "¿Podrías contarme un poco más sobre cómo lo estás sintiendo?"
        )
    
    elif session["emociones_totales_detectadas"] >= 2:
        emociones_list = ", ".join(session["emociones_detectadas"])
        respuesta_original = (
            f"Por lo que mencionás, podría tratarse de un cuadro vinculado a {emociones_list}. "
            "Me interesa saber si notás que esto te afecta en tu vida diaria."
        )
    
    else:
        respuesta_original = (
            "Gracias por compartir lo que estás atravesando. "
            "Si lo deseás, podés contarme más para que pueda orientarte mejor."
        )
    

    if not respuesta_original or not isinstance(respuesta_original, str) or len(respuesta_original.strip()) < 5:
        respuesta_fallback = (
            "¡Ups! No pude generar una respuesta adecuada en este momento. Podés intentar reformular tu mensaje "
            "o escribir directamente al WhatsApp del Lic. Bustamante: +54 911 3310-1186."
        )
        registrar_auditoria_respuesta(user_id, "respuesta vacía", respuesta_fallback, "Fallback por respuesta nula o inválida")
        registrar_respuesta_openai(interaccion_id, respuesta_fallback)
        return {"respuesta": respuesta_fallback, "session": session}

    registrar_auditoria_respuesta(user_id, respuesta_original, respuesta_original)
    registrar_respuesta_openai(interaccion_id, respuesta_original)
    registrar_historial_clinico(
        user_id=user_id,
        emociones=session.get("emociones_detectadas", []),
        sintomas=[],
        tema=None,
        respuesta_openai=respuesta_original,
        sugerencia=None,
        fase_evaluacion=f"interacción {contador}",
        interaccion_id=interaccion_id,
        fecha=datetime.now(),
        fuente="web",
        origen="modulo_clinico",
        eliminado=False,
    )



    return {"respuesta": respuesta_original, "session": session}







# ==============================================================
# 📌 Obtener todas las emociones históricas de un usuario
# ==============================================================
from core.db.conexion import ejecutar_consulta
from sqlalchemy import text  # si quieres seguir usando SQL parametrizado

def obtener_emociones_usuario(user_id):
    """
    Devuelve una lista de emociones históricas para el usuario desde la DB.
    """
    try:
        query = """
            SELECT emocion
            FROM emociones_detectadas
            WHERE user_id = %s
        """
        resultados = ejecutar_consulta(query, (user_id,))
        return [row["emocion"] for row in resultados] if resultados else []
    except Exception as e:
        print(f"⚠️ Error en obtener_emociones_usuario: {e}")
        return []


# ==============================================================
# 📌 Guardar nueva emoción en DB
# ==============================================================
def guardar_emocion_en_db(user_id, emocion, clasificacion):
    """
    Inserta una emoción detectada y su clasificación en la DB.
    """
    try:
        query = """
            INSERT INTO emociones_detectadas (user_id, emocion, clasificacion, fecha)
            VALUES (%s, %s, %s, NOW())
        """
        ejecutar_consulta(query, (user_id, emocion, clasificacion), commit=True)
        print(f"💾 Emoción '{emocion}' registrada para el usuario {user_id}")
    except Exception as e:
        print(f"⚠️ Error al guardar emoción en DB: {e}")


# ==============================================================
# 📌 Clasificar cuadro clínico probable (puede usarse IA)
# ==============================================================
def clasificar_cuadro_clinico(emocion):
    """
    Clasifica la emoción detectada en un cuadro clínico probable.
    """
    clasificacion_map = {
        "ansiedad": "Posible cuadro de ansiedad generalizada",
        "tristeza": "Posible episodio depresivo",
        "miedo": "Posible cuadro de angustia",
        "insomnio": "Posible trastorno del sueño",
        "estres": "Posible cuadro de estrés crónico",
        "deprimido": "Posible episodio depresivo mayor",
        "soledad": "Posible aislamiento emocional"
    }
    return clasificacion_map.get(
        emocion.lower(),
        "Patrón emocional que requiere evaluación profesional por el Lic. Daniel O. Bustamante"
    )


# ==============================================================
# 📌 Determinar malestar predominante
# ==============================================================
def determinar_malestar_predominante(emociones):
    """
    Determina el malestar más frecuente en la lista de emociones.
    """
    from collections import Counter
    if not emociones:
        return None
    conteo = Counter(emociones)
    return conteo.most_common(1)[0][0]



