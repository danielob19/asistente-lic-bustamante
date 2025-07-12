import unicodedata
import re
from core.utils_contacto import obtener_mensaje_contacto

def normalizar(texto: str) -> str:
    texto = texto.lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^\w\s]", "", texto)  # elimina signos de puntuación
    return texto

def procesar_administrativo(mensaje_usuario: str, session: dict, user_id: str) -> dict:
    mensaje_usuario = normalizar(mensaje_usuario)

    RESPUESTAS = [
        {
            "claves": ["obra social", "obras sociales", "prepaga", "osde", "swiss medical", "galeno", "aceptan obra social"],
            "respuesta": (
                "El Lic. Daniel O. Bustamante no trabaja con obras sociales ni prepagas. "
                "Atiende únicamente de manera particular. Si querés coordinar una sesión, podés escribirle al WhatsApp +54 911 3310-1186."
            )
        },
        {
            "claves": ["precio", "valor", "cuanto cuesta", "cuanto cobran", "honorario", "tarifa"],
            "respuesta": (
                "El valor de la sesión puede variar según el tipo de tratamiento (individual o de pareja). "
                "Para conocer el valor actual, podés escribirle directamente al Lic. Bustamante al WhatsApp +54 911 3310-1186."
            )
        },
        {
            "claves": ["que dias", "que horario", "disponibilidad", "cuando atiende", "horarios disponibles"],
            "respuesta": (
                "El Lic. Bustamante atiende de lunes a viernes, entre las 13:00 y las 20:00 hs. "
                "Podés consultarle por disponibilidad escribiéndole directamente al WhatsApp +54 911 3310-1186."
            )
        },
        {
            "claves": ["tratamientos", "que atiende", "tipo de terapia", "que temas atiende"],
            "respuesta": (
                "El Lic. Bustamante es psicólogo especializado en psicología clínica. "
                "Realiza tratamientos psicológicos individuales y también terapia de pareja, siempre en modalidad online."
            )
        },
        {
            "claves": ["contacto", "whatsapp", "como comunicarme", "como contactarlo", "me das el numero"],
            "respuesta": obtener_mensaje_contacto()
        },
        {
            "claves": ["modalidad", "online", "presencial", "videollamada", "zoom", "virtual"],
            "respuesta": (
                "El Lic. Bustamante trabaja exclusivamente en modalidad online, mediante videollamadas. "
                "Si querés saber más o agendar un encuentro, podés escribirle directamente al WhatsApp +54 911 3310-1186."
            )
        },
    ]

    for item in RESPUESTAS:
        if any(p in mensaje_usuario for p in item["claves"]):
            session["ultimas_respuestas"].append(item["respuesta"])
            return {"respuesta": item["respuesta"]}

    # Fallback
    fallback = (
        "Si querés contactar al Lic. Daniel O. Bustamante, podés escribirle directamente al WhatsApp +54 911 3310-1186. "
        "Él podrá responderte personalmente cualquier duda puntual."
    )
    session["ultimas_respuestas"].append(fallback)
    return {"respuesta": fallback}
