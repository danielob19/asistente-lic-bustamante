import openai
import re
import time
import unicodedata
import string
from typing import Dict, Any
from datetime import datetime

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
    registrar_emocion_clinica
)

from core.db.historial import registrar_historial_clinico

from core.db.sintomas import (
    registrar_sintoma,
    obtener_sintomas_existentes
)

from core.db.consulta import (
    obtener_emociones_ya_registradas,
    obtener_historial_clinico_usuario
)

from core.db.conexion import ejecutar_consulta  # Eliminado user_sessions

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
    temas = [h[3] for h in historial if h[3]]
    emociones = [e for h in historial if h[1] for e in h[1]]
    resumen_temas = ", ".join(set(temas)) if temas else "diversos temas"
    resumen_emociones = ", ".join(set(emociones)) if emociones else "varias emociones"
    return f"temas como {resumen_temas} y emociones como {resumen_emociones}"

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

    # Registrar emociones nuevas
    for emocion in emociones_nuevas:
        registrar_emocion(emocion, f"interacción {contador}", user_id)
        session["emociones_detectadas"].append(emocion)
        session["emociones_totales_detectadas"] += 1

        # Evaluar si es la primera interacción clínica del usuario
        if session.get("emociones_totales_detectadas", 0) == 1:
            try:
                registrar_historial_clinico(
                    user_id=user_id,
                    emociones=session.get("emociones_detectadas", []),
                    sintomas=[],
                    tema=None,
                    respuesta_openai="Inicio de registro clínico.",
                    sugerencia=None,
                    fase_evaluacion="interacción inicial",
                    interaccion_id=None,
                    fecha=datetime.now(),
                    fuente="web",
                    eliminado=False
                )
                print("🧠 Historial clínico inicial registrado con éxito.")
            except Exception as e:
                print(f"⚠️ Error al registrar historial clínico inicial: {e}")
    
        try:
            registrar_emocion_clinica(user_id, emocion, origen="detección")
        except Exception as e:
            print(f"🛑 Error al registrar emoción clínica: {e}")
    
    # Registrar historial clínico SIEMPRE que haya emociones detectadas
    if session["emociones_detectadas"]:
        respuesta_clinica = (
            "Gracias por compartir lo que estás atravesando. Si lo deseás, podés contactar al Lic. Bustamante por WhatsApp: +54 911 3310-1186."
        )
        interaccion_id = registrar_interaccion(user_id, mensaje_usuario, mensaje_original)
        registrar_respuesta_openai(interaccion_id, respuesta_clinica)
        registrar_historial_clinico(
            user_id=user_id,
            emociones=session["emociones_detectadas"],
            sintomas=[],
            tema=None,
            respuesta_openai=respuesta_clinica,
            sugerencia="registro inmediato",
            fase_evaluacion=f"interacción {contador}",
            interaccion_id=interaccion_id,
            fecha=datetime.now(),
            fuente="web",
            eliminado=False
        )
        return {"respuesta": respuesta_clinica, "session": session}


#    if session["emociones_totales_detectadas"] >= 3 and not session["emociones_sugerencia_realizada"]:
#        session["emociones_sugerencia_realizada"] = True
#        respuesta_sugerencia = (
#            "Dado lo que venís mencionando, podría tratarse de un cuadro clínico que convendría abordar con mayor profundidad. "
#            "Podés contactar directamente al Lic. Bustamante escribiendo al WhatsApp +54 911 3310-1186."
#        )
#        interaccion_id = registrar_interaccion(user_id, mensaje_usuario, mensaje_original)
#        registrar_respuesta_openai(interaccion_id, respuesta_sugerencia)
#        registrar_historial_clinico(
#            user_id=user_id,
#            emociones=session["emociones_detectadas"],
#            sintomas=[],
#            tema=None,
#            respuesta_openai=respuesta_sugerencia,
#            sugerencia="sugerencia realizada",
#            fase_evaluacion=f"interacción {contador}",
#            interaccion_id=interaccion_id
#        )
#        return {"respuesta": respuesta_sugerencia, "session": session}
    

    # Siempre registrar historial clínico desde la primera emoción detectada
    respuesta_clinica = (
        "Gracias por compartir lo que estás atravesando. Si lo deseás, podés contactar al Lic. Bustamante por WhatsApp: +54 911 3310-1186."
    )
    interaccion_id = registrar_interaccion(user_id, mensaje_usuario, mensaje_original)
    registrar_respuesta_openai(interaccion_id, respuesta_clinica)
    
    registrar_historial_clinico(
        user_id=user_id,
        emociones=session["emociones_detectadas"],
        sintomas=[],
        tema=None,
        respuesta_openai=respuesta_clinica,
        sugerencia="registro inmediato",
        fase_evaluacion=f"interacción {contador}",
        interaccion_id=interaccion_id,
        fecha=datetime.now(),
        fuente="web",
        eliminado=False
    )
    
    return {"respuesta": respuesta_clinica, "session": session}


 #   if session["emociones_totales_detectadas"] >= 10 and not session["emociones_corte_aplicado"]:
 #       session["emociones_corte_aplicado"] = True
 #       respuesta_corte = (
 #           "Gracias por compartir lo que estás atravesando. Por la cantidad de aspectos clínicos mencionados, sería importante conversarlo directamente con un profesional. "
 #           "En este espacio no podemos continuar profundizando. Podés escribir al Lic. Bustamante al WhatsApp +54 911 3310-1186 para coordinar una consulta adecuada."
 #       )
 #       interaccion_id = registrar_interaccion(user_id, mensaje_usuario, mensaje_original)
 #       registrar_respuesta_openai(interaccion_id, respuesta_corte)
 #       registrar_historial_clinico(
 #           user_id=user_id,
 #           emociones=session["emociones_detectadas"],
 #           sintomas=[],
 #           tema=None,
 #           respuesta_openai=respuesta_corte,
 #           sugerencia="corte clínico",
 #           fase_evaluacion=f"interacción {contador}",
 #           interaccion_id=interaccion_id
 #       )
 #       return {"respuesta": respuesta_corte, "session": session}

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
        emociones=session["emociones_detectadas"],
        sintomas=[],
        tema=None,
        respuesta_openai=respuesta_original,
        sugerencia=None,
        fase_evaluacion=f"interacción {contador}",
        interaccion_id=interaccion_id,
        fecha=datetime.now(),
        fuente="web",
        eliminado=False
    )

    return {"respuesta": respuesta_original, "session": session}
