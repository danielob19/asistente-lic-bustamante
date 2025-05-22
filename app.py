# Bloque de verificación de imports críticos
import os
import traceback

IMPORTS_CRITICOS = [
    "openai", "psycopg2", "fastapi", "uvicorn",
    "dotenv", "requests", "pydantic"
]

ruta_log = os.path.join("logs", "test_imports.log")
with open(ruta_log, "w", encoding="utf-8") as log:
    for nombre in IMPORTS_CRITICOS:
        try:
            __import__(nombre)
        except Exception:
            log.write(f"[ERROR] Falló el import de: {nombre}\n")
            log.write(traceback.format_exc() + "\n")



import os
import psycopg2
import threading
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ✅ Inicialización de FastAPI
app = FastAPI()

# 📂 Importar y montar el router de /asistente
from routes.asistente import router as asistente_router
app.include_router(asistente_router)

# 🌐 Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 📌 Constantes utilizadas por el asistente
CLINICO_CONTINUACION = "CLINICO_CONTINUACION"
SALUDO = "SALUDO"
CORTESIA = "CORTESIA"
ADMINISTRATIVO = "ADMINISTRATIVO"
CLINICO = "CLINICO"
CONSULTA_AGENDAR = "CONSULTA_AGENDAR"
CONSULTA_MODALIDAD = "CONSULTA_MODALIDAD"

# 🔑 Clave API de OpenAI desde entorno
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("OPENAI_API_KEY no está configurada en las variables de entorno.")

# 🔗 URL de conexión PostgreSQL desde entorno
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL no está configurada en las variables de entorno.")

# 🧠 Variables de sesión (en memoria)
user_sessions = {}
SESSION_TIMEOUT = 60 * 8  # Tiempo de inactividad para limpieza

# 🧠 Inicialización de síntomas cacheados
sintomas_cacheados = set()

@app.on_event("startup")
def startup_event():
    global sintomas_cacheados

    # 🔁 Inicializa la base de datos si hay lógica adicional (dejar comentado si no aplica)
    # init_db()

    # 🧠 Generar embeddings de FAQ si está disponible
    try:
        from core.faq_semantica import generate_embeddings_faq
        generate_embeddings_faq()
    except Exception:
        pass

    # 🧹 Inicia limpieza de sesiones
    start_session_cleaner()

    # 💾 Cargar cache de síntomas desde la base
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT LOWER(sintoma) FROM palabras_clave")
        sintomas = cursor.fetchall()
        sintomas_cacheados = {s[0].strip() for s in sintomas if s[0]}
        conn.close()
        print(f"✅ Cache inicial de síntomas cargado: {len(sintomas_cacheados)} ítems.")
    except Exception as e:
        print(f"⚠️ Error al inicializar cache de síntomas: {e}")

# 🧽 Limpiador de sesiones inactivas
def start_session_cleaner():
    """
    Elimina sesiones de usuario tras un tiempo de inactividad.
    """
    def cleaner():
        while True:
            current_time = time.time()
            inactivos = [
                user_id for user_id, session in user_sessions.items()
                if current_time - session["ultima_interaccion"] > SESSION_TIMEOUT
            ]
            for user_id in inactivos:
                del user_sessions[user_id]
            time.sleep(30)

    thread = threading.Thread(target=cleaner, daemon=True)
    thread.start()
