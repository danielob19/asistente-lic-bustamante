import re
import unicodedata
import string

def normalizar_texto(texto: str) -> str:
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("utf-8")
    texto = texto.translate(str.maketrans("", "", string.punctuation))
    return texto

# ✅ Función reutilizable de seguridad textual
def contiene_elementos_peligrosos(texto: str) -> bool:
    """
    Detecta si un texto contiene patrones potencialmente peligrosos o maliciosos
    como comandos de sistema, código fuente o expresiones técnicas sensibles.
    """
    texto = normalizar_texto(texto)
    patrones_riesgosos = [
        r"openai\.apikey", r"import\s", r"os\.system", r"eval\(", r"exec\(",
        r"<script", r"</script>", r"\bdrop\b.*\btable\b", r"\bdelete\b.*\bfrom\b",
        r"\brm\s+-rf\b", r"\bchmod\b", r"\bmkfs\b", r"\bshutdown\b", r"\breboot\b",
        r"select\s+.*\s+from", r"insert\s+into", r"update\s+\w+\s+set", r"delete\s+from"
    ]
    return any(re.search(patron, texto, re.IGNORECASE) for patron in patrones_riesgosos)

def contiene_frase_de_peligro(texto: str) -> bool:
    """
    Detecta si un texto contiene frases que indican peligro emocional, psicológico o físico.
    Esta función se enfoca en expresiones que podrían implicar riesgo para el usuario u otros.
    """
    texto = normalizar_texto(texto)
    frases_peligrosas = [
        r"\bme quiero morir\b",
        r"\bno quiero vivir\b",
        r"\bme lastime\b",
        r"\bme hice dano\b",
        r"\btodo me da lo mismo\b",
        r"\bquiero desaparecer\b",
        r"\bno soporto mas\b",
        r"\bestoy al limite\b",
        r"\bme quiero ir\b",
        r"\bya no importa nada\b",
        r"\bme mataria\b",
        r"\bno tiene sentido vivir\b",
        r"\bquisiera estar muerto\b",
        r"\btendria que matarme\b"
    ]
    return any(re.search(frase, texto, re.IGNORECASE) for frase in frases_peligrosas)

def es_input_malicioso(texto: str) -> bool:
    """
    Evalúa si el mensaje del usuario contiene patrones maliciosos típicos
    de código, intentos de inyección o comandos peligrosos.

    Retorna True si detecta contenido sospechoso.
    """
    texto = normalizar_texto(texto)
    patrones_maliciosos = [
        r"(\bimport\b|\bos\b|\bsystem\b|\beval\b|\bexec\b|\bopenai\.apikey\b)",  # Código Python
        r"(\bdrop\b|\bdelete\b|\binsert\b|\bupdate\b).*?\b(table|database)\b",   # SQL Injection
        r"(--|#|;|//).*?(drop|delete|system|rm\s+-rf)",                           # Comentarios maliciosos
        r"<script.*?>|</script>",                                                # HTML/JS malicioso
        r"\b(shutdown|reboot|rm\s+-rf|mkfs|chmod|chown)\b"                        # Comandos Shell peligrosos
    ]
    return any(re.search(patron, texto, re.IGNORECASE) for patron in patrones_maliciosos)

def clasificar_input_inicial(mensaje: str) -> str:
    """
    Clasifica el tipo de mensaje inicial del usuario según su contenido.
    """
    mensaje = normalizar_texto(mensaje)

    if any(palabra in mensaje for palabra in ["hola", "buenas", "que tal", "buen dia", "buenas tardes", "buenas noches"]):
        return "SALUDO"
    elif any(palabra in mensaje for palabra in ["gracias", "ok", "de acuerdo", "entendido", "perfecto", "dale"]):
        return "CORTESIA"
    elif any(palabra in mensaje for palabra in ["turno", "agenda", "cita", "sesion", "consultar", "atencion"]):
        return "CONSULTA_AGENDAR"
    elif any(palabra in mensaje for palabra in ["modalidad", "online", "presencial", "videollamada", "consultorio"]):
        return "CONSULTA_MODALIDAD"
    elif any(palabra in mensaje for palabra in ["sentido", "vacio", "angustia", "ansiedad", "tristeza", "depresion", "duelo", "soledad", "inestabilidad"]):
        return "CLINICO"
    else:
        return "FUERA_DE_CONTEXTO"
