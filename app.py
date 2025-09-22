# app.py — versión corregida
import os
import threading
import time
import logging
import psycopg2
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 🔧 logging básico (opcional, útil para Render/uvicorn)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ Inicialización de FastAPI
app = FastAPI(title="asistente")

# 🌐 Configuración de CORS
origins = [
    "https://licbustamante.com.ar",
    "http://localhost",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 📌 Carga robusta de DATABASE_URL (env → constantes como respaldo)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    try:
        from core.constantes import DATABASE_URL as _DB_FROM_CONST
        DATABASE_URL = _DB_FROM_CONST
    except Exception:
        raise ValueError("DATABASE_URL no está configurada en el entorno ni en core.constantes.")

# 🧠 Variables de sesión (en memoria)
user_sessions: dict[str, dict] = {}
SESSION_TIMEOUT = 60 * 8  # 8 minutos

# 🧠 Inicialización de síntomas cacheados
sintomas_cacheados = set()

# 📂 Importar y montar el router de /asistente
from routes.asistente import router as asistente_router  # noqa: E402
app.include_router(asistente_router)

# 🔌 Startup: FAQ embeddings + limpieza de sesiones + precarga de síntomas
@app.on_event("startup")
def startup_event():
    global sintomas_cacheados

    # 🧠 Generar embeddings de FAQ si está disponible
    try:
        from core.faq_semantica import generate_embeddings_faq  # noqa: WPS433
        generate_embeddings_faq()
    except Exception:
        pass

    # 🧹 Inicia limpieza de sesiones
    start_session_cleaner()

    # 🗂️ Cargar cache de síntomas desde historial
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT LOWER(unnest(emociones)) AS sintoma
            FROM public.historial_clinico_usuario
            WHERE emociones IS NOT NULL
        """)
        sintomas = cursor.fetchall()
        conn.close()

        sintomas_cacheados = {s[0].strip() for s in sintomas if s and s[0]}
        logger.info("✅ Cache de síntomas cargado: %s ítems.", len(sintomas_cacheados))
    except Exception as e:
        logger.warning("⚠️ Error al inicializar cache de síntomas: %s", e)
        sintomas_cacheados = set()

# 🧽 Limpiador de sesiones inactivas
def start_session_cleaner():
    def cleaner():
        while True:
            current_time = time.time()
            inactivos = [
                user_id for user_id, session in list(user_sessions.items())
                if current_time - session.get("ultima_interaccion", 0) > SESSION_TIMEOUT
            ]
            for user_id in inactivos:
                user_sessions.pop(user_id, None)
            time.sleep(30)

    thread = threading.Thread(target=cleaner, daemon=True)
    thread.start()

# ✅ Endpoint raíz para evitar 404 y verificar estado básico
@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "asistente",
        "endpoints": {
            "POST /asistente": "Procesa la interacción del usuario",
            "GET /health": "Chequeo de salud simple",
        },
    }

# ✅ Healthcheck simple (útil para Render/monitoreo)
@app.get("/health")
def health():
    try:
        # intento liviano de conexión
        conn = psycopg2.connect(DATABASE_URL)
        conn.close()
        db = "ok"
    except Exception:
        db = "fail"
    return {"status": "ok", "db": db}

