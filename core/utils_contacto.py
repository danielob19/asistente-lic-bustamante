from core.db.registro import registrar_auditoria_input_original
import unicodedata
import string

def normalizar_texto(texto: str) -> str:
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("utf-8")
    texto = texto.translate(str.maketrans("", "", string.punctuation))
    return texto

def es_consulta_contacto(mensaje: str, user_id: str = None, mensaje_original: str = None) -> bool:
    """
    Detecta si el mensaje hace referencia al deseo de contactar al profesional.
    Si hay coincidencia y se proporciona `user_id` y `mensaje_original`, registra la auditoría automáticamente.
    """
    if not mensaje or not isinstance(mensaje, str):
        return False

    mensaje_normalizado = normalizar_texto(mensaje)

    expresiones_contacto = [
        "contacto", "numero", "whatsapp", "telefono",
        "como lo contacto", "quiero contactarlo", "como me comunico",
        "quiero escribirle", "quiero hablar con el", "me das el numero",
        "como se agenda", "como saco turno", "quiero pedir turno",
        "necesito contactarlo", "como empiezo la terapia", "quiero empezar la consulta",
        "como me comunico con el licenciado", "mejor psicologo", "mejor terapeuta",
        "atienden estos casos", "atiende casos", "trata casos", "atiende temas",
        "trata temas", "atiende estos", "trata estos", "atiende estos temas"
    ]

    hay_coincidencia = any(exp in mensaje_normalizado for exp in expresiones_contacto)

    if hay_coincidencia and user_id and mensaje_original:
        registrar_auditoria_input_original(user_id, mensaje_original, mensaje_normalizado, "CONSULTA_CONTACTO")

    return hay_coincidencia


def obtener_mensaje_contacto():
    return (
        "En caso de que desees contactar al Lic. Daniel O. Bustamante, "
        "podés hacerlo escribiéndole al WhatsApp +54 911 3310-1186, que con gusto responderá a tus inquietudes."
    )
