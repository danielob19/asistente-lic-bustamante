import re

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
