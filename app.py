import os
import psycopg2
from core.constantes import DATABASE_URL
import threading
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ✅ Inicialización de FastAPI
app = FastAPI()

# 🌐 Configuración de CORS (aplicar solo a app, NO a router)
origins = [
    "https://licbustamante.com.ar",
    "http://localhost",
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 📂 Importar y montar el router de /asistente
from routes.asistente import router as asistente_router
app.include_router(asistente_router)

# 📌 Constantes utilizadas por el asistente (pueden migrarse a constantes.py si no se usan aquí directamente)
CLINICO_CONTINUACION = "CLINICO_CONTINUACION"
SALUDO = "SALUDO"
CORTESIA = "CORTESIA"
ADMINISTRATIVO = "ADMINISTRATIVO"
CLINICO = "CLINICO"
CONSULTA_AGENDAR = "CONSULTA_AGENDAR"
CONSULTA_MODALIDAD = "CONSULTA_MODALIDAD"

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

    # 🧠 Generar embeddings de FAQ si está disponible
    try:
        from core.faq_semantica import generate_embeddings_faq
        generate_embeddings_faq()
    except Exception:
        pass

    # 🧹 Inicia limpieza de sesiones
    start_session_cleaner()

    
    # 🗂️ Cargar cache de síntomas desde la base (desde historial_clinico_usuario)
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT LOWER(unnest(emociones)) AS sintoma
            FROM historial_clinico_usuario
            WHERE emociones IS NOT NULL
        """)
        sintomas = cursor.fetchall()
        conn.close()

        sintomas_cacheados = {s[0].strip() for s in sintomas if s and s[0]}
        print(f"✅ Cache inicial de síntomas cargado desde historial: {len(sintomas_cacheados)} ítems.")
    except Exception as e:
        print(f"⚠️ Error al inicializar cache de síntomas (historial): {e}")
        sintomas_cacheados = set()



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
                if current_time - session.get("ultima_interaccion", 0) > SESSION_TIMEOUT
            ]
            for user_id in inactivos:
                del user_sessions[user_id]
            time.sleep(30)

    thread = threading.Thread(target=cleaner, daemon=True)
    thread.start()

