import re
import time
import unicodedata
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

def procesar_clinico(input_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Procesa mensajes clínicos: detecta emociones, realiza inferencias con OpenAI,
    registra resultados en PostgreSQL y devuelve una respuesta filtrada y profesional.

    :param input_data: Diccionario con claves: mensaje_original, mensaje_usuario, user_id, session, contador
    :return: Diccionario con respuesta final {"respuesta": ...}
    """

    mensaje_original = input_data["mensaje_original"]
    mensaje_usuario = input_data["mensaje_usuario"]
    user_id = input_data["user_id"]
    session = input_data["session"]
    contador = input_data["contador"]

    sintomas_existentes = obtener_sintomas_existentes()
    emociones_detectadas = detectar_emociones_negativas(mensaje_usuario) or []

    emociones_nuevas = []
    for emocion in emociones_detectadas:
        emocion = re.sub(r'[^\w\sáéíóúüñ]+$', '', emocion.lower().strip())
        if emocion not in session["emociones_detectadas"]:
            if emocion not in sintomas_existentes:
                emociones_nuevas.append(emocion)
                registrar_sintoma(emocion)

    for emocion in emociones_nuevas:
        registrar_emocion(emocion, f"interacción {contador}", user_id)
        session["emociones_detectadas"].append(emocion)

    # Registrar solo las emociones nuevas en la base de datos con un cuadro clínico asignado por OpenAI
    for emocion in emociones_nuevas:
        # Generar el prompt para OpenAI
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

    # Confirmación final de emociones registradas
    if emociones_nuevas:
        print(f"✅ Se registraron las siguientes emociones nuevas en palabras_clave: {emociones_nuevas}")
    else:
        print("✅ No hubo emociones nuevas para registrar en palabras_clave.")
    
    # Evitar agregar duplicados
    nuevas_emociones = [e for e in emociones_detectadas if e not in session["emociones_detectadas"]]
    session["emociones_detectadas"].extend(nuevas_emociones)
    
    # Registrar emociones en la base si no están registradas
    emociones_registradas_bd = obtener_emociones_ya_registradas(user_id, contador)
    
    for emocion in session["emociones_detectadas"]:
        if emocion not in emociones_registradas_bd:
            registrar_emocion(emocion, f"interacción {contador}", user_id)

    interaccion_id = registrar_interaccion(user_id, mensaje_usuario, mensaje_original)

    prompt = (
        f"Mensaje recibido del usuario: '{mensaje_usuario}'.\n"
        "Redactá una respuesta breve, profesional y clínica como si fueras el asistente virtual del Lic. Daniel O. Bustamante, psicólogo.\n"
        "Estilo y directrices obligatorias:\n"
        "- Mantené un tono clínico, sobrio, profesional y respetuoso.\n"
        "- Comenzá la respuesta con un saludo breve como 'Hola, ¿qué tal?' solo si es la interacción 1.\n"
        "- Si se detecta malestar emocional, formulá una observación objetiva con expresiones como: 'se observa...', 'impresiona...', 'podría tratarse de...', etc.\n"
        "- No uses frases motivacionales ni simulaciones empáticas (ej: 'te entiendo', 'todo va a estar bien', etc.).\n"
        "- No uses lenguaje institucional ni brindes información administrativa.\n"
        "- Si el mensaje no tiene contenido clínico, devolvé una frase neutra como: 'Gracias por tu mensaje. ¿Hay algo puntual que te gustaría compartir o consultar en este espacio?'\n"
        f"- IMPORTANTE: estás en la interacción {contador}.\n"
    )

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
