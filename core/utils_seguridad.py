import re

# ✅ Función reutilizable de seguridad textual
def contiene_elementos_peligrosos(texto: str) -> bool:
    """
    Detecta si un texto contiene patrones potencialmente peligrosos o maliciosos
    como comandos de sistema, código fuente o expresiones técnicas sensibles.
    """
    patrones_riesgosos = [
        r"openai\.api_key", r"import\s", r"os\.system", r"eval\(", r"exec\(",
        r"<script", r"</script>", r"\bdrop\b.*\btable\b", r"\bdelete\b.*\bfrom\b",
        r"\brm\s+-rf\b", r"\bchmod\b", r"\bmkfs\b", r"\bshutdown\b", r"\breboot\b",
        r"SELECT\s+.*\s+FROM", r"INSERT\s+INTO", r"UPDATE\s+\w+\s+SET", r"DELETE\s+FROM"
    ]
    return any(re.search(patron, texto, re.IGNORECASE) for patron in patrones_riesgosos)

def contiene_frase_de_peligro(texto: str) -> bool:
    """
    Detecta si un texto contiene frases que indican peligro emocional, psicológico o físico.
    Esta función se enfoca en expresiones que podrían implicar riesgo para el usuario u otros.
    """
    frases_peligrosas = [
        r"\bme quiero morir\b",
        r"\bno quiero vivir\b",
        r"\bme lastimé\b",
        r"\bme hice daño\b",
        r"\btodo me da lo mismo\b",
        r"\bquiero desaparecer\b",
        r"\bno soporto más\b",
        r"\bestoy al límite\b",
        r"\bme quiero ir\b",
        r"\bya no importa nada\b",
        r"\bme mataría\b",
        r"\bno tiene sentido vivir\b",
        r"\bquisiera estar muerto\b",
        r"\btendría que matarme\b"
    ]
    return any(re.search(frase, texto, re.IGNORECASE) for frase in frases_peligrosas)


def es_input_malicioso(texto: str) -> bool:
    """
    Evalúa si el mensaje del usuario contiene patrones maliciosos típicos
    de código, intentos de inyección o comandos peligrosos.

    Retorna True si detecta contenido sospechoso.
    """
    patrones_maliciosos = [
        r"(\bimport\b|\bos\b|\bsystem\b|\beval\b|\bexec\b|\bopenai\.api_key\b)",  # Código Python
        r"(\bdrop\b|\bdelete\b|\binsert\b|\bupdate\b).*?\b(table|database)\b",     # SQL Injection
        r"(--|#|;|//).*?(drop|delete|system|rm\s+-rf)",                             # Comentarios maliciosos
        r"<script.*?>|</script>",                                                  # HTML/JS malicioso
        r"\b(shutdown|reboot|rm\s+-rf|mkfs|chmod|chown)\b"                          # Comandos Shell peligrosos
    ]
    for patron in patrones_maliciosos:
        if re.search(patron, texto, re.IGNORECASE):
            return True
    return False
