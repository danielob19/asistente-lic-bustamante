# core/utils/modulo_administrativo.py

from core.utils_contacto import obtener_mensaje_contacto

def procesar_administrativo(mensaje_usuario: str, session: dict, user_id: str) -> dict:
    """
    Procesa preguntas administrativas comunes (obras sociales, honorarios, horarios, modalidad, contacto, etc.)
    Devuelve una respuesta lista para ser enviada.
    """

    respuesta = None

    if any(p in mensaje_usuario for p in ["obra social", "prepaga", "osde", "swiss medical", "galeno"]):
        respuesta = (
            "El Lic. Daniel O. Bustamante no trabaja con obras sociales ni prepagas. "
            "Atiende únicamente de manera particular. Si querés coordinar una sesión, podés escribirle al WhatsApp +54 911 3310-1186."
        )

    elif any(p in mensaje_usuario for p in ["precio", "valor", "cuánto cuesta", "cuanto cuesta", "honorario"]):
        respuesta = (
            "El valor de la sesión puede variar según el tipo de tratamiento (individual o de pareja). "
            "Para conocer el valor actual, podés escribirle directamente al Lic. Bustamante al WhatsApp +54 911 3310-1186."
        )

    elif any(p in mensaje_usuario for p in ["qué días", "qué horario", "disponibilidad", "cuando atiende"]):
        respuesta = (
            "El Lic. Bustamante atiende de lunes a viernes, entre las 13:00 y las 20:00 hs. "
            "Para coordinar un horario, podés escribirle directamente al WhatsApp +54 911 3310-1186."
        )

    elif any(p in mensaje_usuario for p in ["tratamientos", "qué atiende", "tipo de terapia"]):
        respuesta = (
            "El Lic. Bustamante es psicólogo especializado en psicología clínica. "
            "Realiza tratamientos psicológicos individuales y terapia de pareja."
        )

    elif "contacto" in mensaje_usuario or "whatsapp" in mensaje_usuario or "cómo comunicarme" in mensaje_usuario:
        respuesta = obtener_mensaje_contacto()

    # Fallback genérico
    if not respuesta:
        respuesta = (
            "Gracias por tu consulta. Si querés coordinar una sesión, podés escribirle al Lic. Bustamante al WhatsApp +54 911 3310-1186."
        )

    session["ultimas_respuestas"].append(respuesta)
    return {"respuesta": respuesta}
