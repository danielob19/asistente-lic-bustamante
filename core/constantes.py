import os

# ✅ Ruta de conexión a la base de datos (Render la define automáticamente como variable de entorno)
DATABASE_URL = os.getenv("DATABASE_URL")

# 🔒 Protección en caso de que no esté definida
if DATABASE_URL is None:
    raise ValueError("La variable de entorno DATABASE_URL no está definida.")

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

# ⏱ Tiempo de expiración de sesiones (en segundos)
SESSION_TIMEOUT = 60

# 🗂 Cache de síntomas (se llena al iniciar la app)
sintomas_cacheados = set()

# ❌ Lista de palabras irrelevantes para análisis clínico
palabras_irrelevantes = {
    "un", "una", "el", "la", "lo", "es", "son", "estoy", "siento", "me siento", "tambien", "tambien tengo", "que",
    "de", "en", "por", "a", "me", "mi", "tengo", "mucho", "muy", "un", "poco", "tengo", "animicos", "si", "supuesto",
    "frecuentes", "verdad", "sé", "hoy", "quiero", "bastante", "gente", "frecuencia", "entendí",
    "hola", "estoy", "vos", "entiendo", "soy", "mi", "de", "es", "4782-6465", "me", "siento", "para", "mucha", "y",
    "sufro", "vida", "que", "opinás", "¿", "?", "reinicia", "con", "del", "necesito", "me", "das"
}
