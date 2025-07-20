import openai
import re
import time
import unicodedata
import string
from typing import Dict, Any

from core.utils.clinico_contexto import hay_contexto_clinico_anterior
from core.utils_contacto import obtener_mensaje_contacto
from core.funciones_asistente import detectar_emociones_negativas
from core.utils.generador_openai import generar_respuesta_con_openai
from core.constantes import CLINICO, CLINICO_CONTINUACION
from core.db.registro import (
    registrar_respuesta_openai,
    registrar_auditoria_respuesta,
    registrar_interaccion,
    registrar_emocion
)
from core.db.sintomas import (
    registrar_sintoma,
    obtener_sintomas_existentes
)
from core.db.consulta import obtener_emociones_ya_registradas

from core.contexto import user_sessions

# Función auxiliar para normalizar texto
def normalizar_texto(texto: str) -> str:
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("utf-8")
    texto = texto.translate(str.maketrans("", "", string.punctuation))
    return texto

def procesar_clinico(input_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Procesa mensajes clínicos: detecta emociones, realiza inferencias con OpenAI,
    registra resultados en PostgreSQL y devuelve una respuesta filtrada y profesional.

    :param input_data: Diccionario con claves: mensaje_original, mensaje_usuario, user_id, session, contador
    :return: Diccionario con respuesta final {"respuesta": ...}
    """

    mensaje_original = input_data["mensaje_original"]
    mensaje_usuario = normalizar_texto(input_data["mensaje_usuario"])
    user_id = input_data["user_id"]
    session = input_data["session"]
    contador = input_data["contador"]

    sintomas_existentes = {normalizar_texto(s) for s in obtener_sintomas_existentes()}
    emociones_detectadas = detectar_emociones_negativas(mensaje_usuario) or []

    # Inicializar contadores y flags de sesión si aún no existen
    session.setdefault("emociones_detectadas", [])
    session.setdefault("emociones_totales_detectadas", 0)
    session.setdefault("emociones_sugerencia_realizada", False)
    session.setdefault("emociones_corte_aplicado", False)
    
    emociones_nuevas = []
    emociones_detectadas_normalizadas = [normalizar_texto(e) for e in emociones_detectadas]
    
    for emocion in emociones_detectadas_normalizadas:
        if emocion not in {normalizar_texto(e) for e in session["emociones_detectadas"]}:
            emociones_nuevas.append(emocion)
            if emocion not in sintomas_existentes:
                registrar_sintoma(emocion)
    
    # Registrar emociones nuevas y acumular en sesión
    for emocion in emociones_nuevas:
        registrar_emocion(emocion, f"interacción {contador}", user_id)
        session["emociones_detectadas"].append(emocion)
        session["emociones_totales_detectadas"] += 1

    # Lógica de sugerencia clínica tras 3 emociones detectadas
    if session["emociones_totales_detectadas"] >= 3 and not session["emociones_sugerencia_realizada"]:
        session["emociones_sugerencia_realizada"] = True
        respuesta_sugerencia = (
            "Dado lo que venís mencionando, podría tratarse de un cuadro clínico que convendría abordar con mayor profundidad. "
            "Podés contactar directamente al Lic. Bustamante escribiendo al WhatsApp +54 911 3310-1186."
        )
        registrar_respuesta_openai(registrar_interaccion(user_id, mensaje_usuario, mensaje_original), respuesta_sugerencia)
        return {"respuesta": respuesta_sugerencia}
    
    # Lógica de corte definitivo tras 10 emociones detectadas
    if session["emociones_totales_detectadas"] >= 10 and not session["emociones_corte_aplicado"]:
        session["emociones_corte_aplicado"] = True
        respuesta_corte = (
            "Gracias por compartir lo que estás atravesando. Por la cantidad de aspectos clínicos mencionados, sería importante conversarlo directamente con un profesional. "
            "En este espacio no podemos continuar profundizando. Podés escribir al Lic. Bustamante al WhatsApp +54 911 3310-1186 para coordinar una consulta adecuada."
        )
        registrar_respuesta_openai(registrar_interaccion(user_id, mensaje_usuario, mensaje_original), respuesta_corte)
        return {"respuesta": respuesta_corte}
    

    for emocion in emociones_nuevas:
        registrar_emocion(emocion, f"interacción {contador}", user_id)
        session["emociones_detectadas"].append(emocion)

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

    if emociones_nuevas:
        print(f"✅ Se registraron las siguientes emociones nuevas en palabras_clave: {emociones_nuevas}")
    else:
        print("✅ No hubo emociones nuevas para registrar en palabras_clave.")

    nuevas_emociones = [normalizar_texto(e) for e in emociones_detectadas if normalizar_texto(e) not in {normalizar_texto(x) for x in session["emociones_detectadas"]}]
    session["emociones_detectadas"].extend(nuevas_emociones)

    emociones_registradas_bd = obtener_emociones_ya_registradas(user_id, contador)
    emociones_registradas_bd = {normalizar_texto(e) for e in emociones_registradas_bd}

    # Registrar solo emociones nuevas no repetidas (evita duplicaciones)
    emociones_para_registrar = [
        e for e in session["emociones_detectadas"]
        if normalizar_texto(e) not in emociones_registradas_bd
    ]
    
    for emocion in emociones_para_registrar:
        registrar_emocion(emocion, f"interacción {contador}", user_id)


    interaccion_id = registrar_interaccion(user_id, mensaje_usuario, mensaje_original)

    # 🧠 Generar prompt clínico personalizado según estado de sesión
    if session["emociones_corte_aplicado"]:
        prompt = (
            f"El usuario ha alcanzado el máximo de interacciones clínicas permitidas.\n"
            "Redactá una última respuesta breve, respetuosa y profesional indicando que no podés continuar conversando por este medio y que sería conveniente derivar la consulta directamente al Lic. Bustamante.\n"
            "No brindes más observaciones clínicas ni sugerencias. No repitas saludos ni agradecimientos."
        )
    elif session["emociones_sugerencia_realizada"]:
        prompt = (
            f"Mensaje recibido del usuario: '{mensaje_usuario}'.\n"
            "Redactá una respuesta clínica breve, sobria y profesional como si fueras el asistente virtual del Lic. Daniel O. Bustamante, psicólogo.\n"
            "Directrices:\n"
            "- Ya sugeriste consultar al profesional. No repitas esa sugerencia.\n"
            "- Si se detecta más malestar, podés mencionar brevemente que se observa una ampliación del cuadro emocional.\n"
            "- Estilo sobrio, sin lenguaje empático ni motivacional.\n"
            f"- Interacción número: {contador}."
        )
    else:
        prompt = (
            f"Mensaje recibido del usuario: '{mensaje_usuario}'.\n"
            "Redactá una respuesta breve, profesional y clínica como si fueras el asistente virtual del Lic. Daniel O. Bustamante, psicólogo.\n"
            "Estilo y directrices obligatorias:\n"
            "- Mantené un tono clínico, sobrio, profesional y respetuoso.\n"
            "- Comenzá la respuesta con un saludo breve como 'Hola, ¿qué tal?' solo si es la interacción 1.\n"
            "- Si se detecta malestar emocional, formulá una observación objetiva con expresiones como: 'se observa...', 'impresiona...', 'podría tratarse de...', etc.\n"
            "- No uses frases motivacionales ni simulaciones empáticas (ej: 'te entiendo', 'todo va a estar bien', etc.).\n"
            "- No uses lenguaje institucional ni brindes información administrativa.\n"
            f"- IMPORTANTE: estás en la interacción {contador}."
        )

    # Activar flags de sugerencia o corte clínico si se supera umbral
    if len(session["emociones_detectadas"]) >= 3 and not session["emociones_sugerencia_realizada"]:
        session["emociones_sugerencia_realizada"] = True
        print("⚠️ Se alcanzó el umbral de 3 emociones. Se activa 'emociones_sugerencia_realizada'.")
    
    if len(session["emociones_detectadas"]) >= 6 and not session["emociones_corte_aplicado"]:
        session["emociones_corte_aplicado"] = True
        print("⛔ Se alcanzó el umbral de 6 emociones. Se activa 'emociones_corte_aplicado'.")
    


    respuesta_original = generar_respuesta_con_openai(prompt, contador, user_id, mensaje_usuario, mensaje_original)

    if not respuesta_original or not isinstance(respuesta_original, str) or len(respuesta_original.strip()) < 5:
        respuesta_fallback = (
            "¡Ups! No pude generar una respuesta adecuada en este momento. Podés intentar reformular tu mensaje "
            "o escribir directamente al WhatsApp del Lic. Bustamante: +54 911 3310-1186."
        )
        registrar_auditoria_respuesta(user_id, "respuesta vacía", respuesta_fallback, "Fallback por respuesta nula o inválida")
        registrar_respuesta_openai(interaccion_id, respuesta_fallback)
        return {"respuesta": respuesta_fallback}

    registrar_auditoria_respuesta(user_id, respuesta_original, respuesta_original)
    registrar_respuesta_openai(interaccion_id, respuesta_original)

    return {"respuesta": respuesta_original}
