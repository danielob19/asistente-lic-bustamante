# ✅ Inicialización de FastAPI
app = FastAPI()

# 🚪 Importar y montar el router de /asistente
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

CLINICO_CONTINUACION = "CLINICO_CONTINUACION"
SALUDO = "SALUDO"
CORTESIA = "CORTESIA"
ADMINISTRATIVO = "ADMINISTRATIVO"
CLINICO = "CLINICO"
CONSULTA_AGENDAR = "CONSULTA_AGENDAR"
CONSULTA_MODALIDAD = "CONSULTA_MODALIDAD"

# 🔑 Configuración de la clave de API de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("OPENAI_API_KEY no está configurada en las variables de entorno.")

# 🔗 Configuración de la URL de la base de datos PostgreSQL
DATABASE_URL = "postgresql://<TU_URL_AQUÍ>"

# 🕒 Gestión de sesiones (en memoria)
user_sessions = {}
SESSION_TIMEOUT = 60 * 8  # Tiempo en segundos para limpiar sesiones inactivas


@app.on_event("startup")
def startup_event():
    global sintomas_cacheados
    sintomas_cacheados = set()

    # 🔁 Inicializa la base de datos
    init_db()
    # 🧠 Genera embeddings de Faq al iniciar
    generate_embeddings_faq()
    # 🧹 Limpia sesiones inactivas
    start_session_cleaner()

    # 🧠 Inicializar cache de síntomas registrados
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


# 🧹 Función para limpiar sesiones inactivas
def start_session_cleaner():
    """
    Limpia las sesiones inactivas después de un tiempo definido (SESSION_TIMEOUT).
    """
    def cleaner():
        while True:
            current_time = time.time()
            inactive_users = [
                user_id for user_id, session in user_sessions.items()
                if current_time - session["ultima_interaccion"] > SESSION_TIMEOUT
            ]
            for user_id in inactive_users:
                del user_sessions[user_id]
            time.sleep(30)  # Intervalo para revisar las sesiones

    thread = threading.Thread(target=cleaner, daemon=True)
    thread.start()
