# core/utils/modulo_clinico.py

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

    # Obtener lista de síntomas ya registrados en la base de datos
    sintomas_existentes = obtener_sintomas_existentes()

    # Detectar emociones desde el mensaje actual
    emociones_detectadas = detectar_emociones_negativas(mensaje_usuario) or []

    # Filtrar emociones detectadas para evitar registrar duplicados
    emociones_nuevas = []
    for emocion in emociones_detectadas:
        emocion = emocion.lower().strip()
        emocion = re.sub(r'[^\w\sáéíóúüñ]+$', '', emocion)

        # Verificar si la emoción ya fue detectada en la sesión
        if emocion not in session["emociones_detectadas"]:
            # Si la emoción no está en la base de datos, agregarla y registrarla
            if emocion not in sintomas_existentes:
                emociones_nuevas.append(emocion)
                registrar_sintoma(emocion)  # ✅ Registrar solo si no existe

    # ✅ Esta función será extendida para:
    # - Registrar en PostgreSQL
    # - Obtener cuadro clínico por OpenAI
    # - Generar respuesta clínica profesional
    # - Registrar auditoría y respuesta final

    return {
        "respuesta": (
            "El módulo clínico ha sido activado correctamente. Falta completar el procesamiento completo."
        )
    }
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
