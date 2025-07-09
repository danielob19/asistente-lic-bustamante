# core/utils/modulo_administrativo.py

from core.utils_contacto import obtener_mensaje_contacto

def procesar_administrativo(mensaje_usuario: str, session: dict, user_id: str) -> dict:
    """
    Procesa preguntas administrativas comunes: obras sociales, honorarios, horarios, tratamientos, contacto, modalidad, etc.
    Devuelve una respuesta lista para ser enviada.
    """

    respuesta = None

    if any(p in mensaje_usuario for p in ["obra social", "prepaga", "osde", "swiss medical", "galeno"]):
        respuesta = (
            "El Lic. Daniel O. Bustamante no trabaja con obras sociales ni prepagas. "
            "Atiende únicamente de manera particular. Si querés coordinar una sesión, podés escribirle al WhatsApp +54 911 3310-1186."
        )

    elif any(p in mensaje_usuario for p in ["precio", "valor", "cuánto cuesta", "cuanto cuesta", "honorario", "tarifa"]):
        respuesta = (
            "El valor de la sesión puede variar según el tipo de tratamiento (individual o de pareja). "
            "Para conocer el valor actual, podés escribirle directamente al Lic. Bustamante al WhatsApp +54 911 3310-1186."
        )

    elif any(p in mensaje_usuario for p in ["qué días", "qué horario", "disponibilidad", "cuando atiende", "qué horarios", "en qué días"]):
        respuesta = (
            "El Lic. Bustamante atiende de lunes a viernes, entre las 13:00 y las 20:00 hs. "
            "Podés consultarle por disponibilidad escribiéndole directamente al WhatsApp +54 911 3310-1186."
        )

    elif any(p in mensaje_usuario for p in ["tratamientos", "qué atiende", "tipo de terapia"]):
        respuesta = (
            "El Lic. Bustamante es psicólogo especializado en psicología clínica. "
            "Realiza tratamientos psicológicos individuales y también terapia de pareja, siempre en modalidad online."
        )

    elif any(p in mensaje_usuario for p in ["contacto", "whatsapp", "cómo comunicarme", "cómo contactarlo"]):
        respuesta = obtener_mensaje_contacto()

    elif any(p in mensaje_usuario for p in ["modalidad", "online", "presencial", "videollamada", "zoom"]):
        respuesta = (
            "El Lic. Bustamante trabaja exclusivamente en modalidad online, mediante videollamadas. "
            "Si querés saber más o agendar un encuentro, podés escribirle directamente al WhatsApp +54 911 3310-1186."
        )

    # Fallback profesional neutro
    if not respuesta:
        respuesta = (
            "Si querés contactar al Lic. Daniel O. Bustamante, podés escribirle directamente al WhatsApp +54 911 3310-1186. "
            "Él podrá responderte personalmente cualquier duda puntual."
        )

    session["ultimas_respuestas"].append(respuesta)
    return {"respuesta": respuesta}
