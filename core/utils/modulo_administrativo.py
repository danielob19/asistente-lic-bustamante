import re
import unicodedata
import openai
from core.utils_contacto import obtener_mensaje_contacto

# Normaliza el texto para minimizar errores por tildes o puntuación
def normalizar(texto: str) -> str:
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("utf-8")
    texto = re.sub(r"[^\w\s]", "", texto)
    return texto

# Diccionario de respuestas por categoría
RESPUESTAS = {
    "obras sociales": (
        "El Lic. Daniel O. Bustamante no trabaja con obras sociales ni prepagas. "
        "Atiende únicamente de manera particular. Si querés coordinar una sesión, podés escribirle al WhatsApp +54 911 3310-1186."
    ),
    "honorarios": (
        "El valor de la sesión puede variar según el tipo de tratamiento (individual o de pareja). "
        "Para conocer el valor actual, podés escribirle directamente al Lic. Bustamante al WhatsApp +54 911 3310-1186."
    ),
    "horarios": (
        "El Lic. Bustamante atiende de lunes a viernes, entre las 13:00 y las 20:00 hs. "
        "Podés consultarle por disponibilidad escribiéndole directamente al WhatsApp +54 911 3310-1186."
    ),
    "tratamientos": (
        "El Lic. Bustamante es psicólogo especializado en psicología clínica. "
        "Realiza tratamientos psicológicos individuales y también terapia de pareja, siempre en modalidad online."
    ),
    "contacto": obtener_mensaje_contacto(),
    "modalidad": (
        "El Lic. Bustamante trabaja exclusivamente en modalidad online, mediante videollamadas. "
        "Si querés saber más o agendar un encuentro, podés escribirle directamente al WhatsApp +54 911 3310-1186."
    )
}

def clasificar_tema_administrativo(mensaje: str) -> str:
    """
    Usa OpenAI para clasificar el mensaje dentro de una categoría administrativa.
    """
    prompt = (
        "Clasificá el siguiente mensaje dentro de una de estas categorías administrativas:\n\n"
        "- obras sociales\n"
        "- honorarios\n"
        "- horarios\n"
        "- tratamientos\n"
        "- contacto\n"
        "- modalidad\n"
        "- otro\n\n"
        "Devolvé solo el nombre de la categoría más adecuada, sin explicaciones ni frases adicionales.\n\n"
        f"Mensaje: {mensaje}"
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0.0
        )
        clasificacion = response.choices[0].message['content'].strip().lower()
        return clasificacion
    except Exception as e:
        print(f"❌ Error al clasificar tema administrativo: {e}")
        return "otro"

def procesar_administrativo(mensaje_usuario: str, session: dict, user_id: str) -> dict:
    """
    Clasifica el mensaje usando OpenAI y devuelve la respuesta administrativa correspondiente.
    También maneja casos especiales como la consulta por atención presencial.
    """
    mensaje_normalizado = normalizar(mensaje_usuario)

    # 🔍 MANEJO ESPECIAL: consulta por atención presencial
    if "presencial" in mensaje_normalizado or "consultorio" in mensaje_normalizado or "forma presencial" in mensaje_normalizado:
        respuesta = (
            "El Lic. Bustamante trabaja exclusivamente en modalidad Online, a través de videollamadas. "
            "No atiende de forma presencial. Podés escribirle al WhatsApp +54 911 3310-1186 si querés más información."
        )
        session["ultimas_respuestas"].append(respuesta)
        session["contador_interacciones"] += 1
        return {"respuesta": respuesta}

    # 🔍 CLASIFICACIÓN por OpenAI
    categoria = clasificar_tema_administrativo(mensaje_normalizado)
    respuesta = RESPUESTAS.get(categoria)

    # 🔄 Si no se reconoció la categoría, usar fallback genérico
    if not respuesta:
        respuesta = (
            "Si querés contactar al Lic. Daniel O. Bustamante, podés escribirle directamente al WhatsApp +54 911 3310-1186. "
            "Él podrá responderte personalmente cualquier duda puntual."
        )

    session["ultimas_respuestas"].append(respuesta)
    session["contador_interacciones"] += 1
    return {"respuesta": respuesta}
