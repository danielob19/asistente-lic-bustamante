# core/constantes.py

# 🎯 Etiquetas de clasificación
CLINICO_CONTINUACION = "CLINICO_CONTINUACION"
SALUDO = "SALUDO"
CORTESIA = "CORTESIA"
ADMINISTRATIVO = "ADMINISTRATIVO"
CLINICO = "CLINICO"
CONSULTA_AGENDAR = "CONSULTA_AGENDAR"
CONSULTA_MODALIDAD = "CONSULTA_MODALIDAD"

# 🧠 Diccionario de sesiones (en memoria)
user_sessions = {}

# ⏱️ Tiempo de expiración de sesiones (en segundos)
SESSION_TIMEOUT = 60

# 📌 Lista de palabras irrelevantes para análisis clínico
palabras_irrelevantes = {
    "un", "una", "el", "la", "lo", "es", "son", "estoy", "siento", "me siento", "tambien", "tambien tengo", "que",
    "de", "en", "por", "a", "me", "mi", "tengo", "mucho", "muy", "un", "poco", "tengo", "animicos", "si", "supuesto",
    "frecuentes", "verdad", "sé", "hoy", "quiero", "bastante", "mucho", "tambien", "gente", "frecuencia", "entendi",
    "hola", "estoy", "vos", "entiendo", "soy", "mi", "de", "es", "4782-6465", "me", "siento", "para", "mucha", "y",
    "sufro", "vida", "que", "opinas", "¿", "?", "reinicia", "con", "del", "necesito", "me", "das"
}

# 🧠 Cache de síntomas (se llena al iniciar la app)
sintomas_cacheados = set()
