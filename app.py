import os
import time
import threading
import sqlite3
import openai
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
import shutil

# Configuración de la clave de API de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("OPENAI_API_KEY no está configurada en las variables de entorno.")

# Inicialización de FastAPI
app = FastAPI()

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ruta para la base de datos
DB_PATH = "/var/data/palabras_clave.db"
PRUEBA_PATH = "/var/data/prueba_escritura.txt"

# Configuración de la base de datos SQLite
def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS palabras_clave (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                palabra TEXT UNIQUE NOT NULL,
                categoria TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interacciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                consulta TEXT NOT NULL,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
        print(f"Base de datos creada o abierta en: {DB_PATH}")
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")

# Verificar escritura en disco
def verificar_escritura_en_disco():
    try:
        with open(PRUEBA_PATH, "w") as archivo:
            archivo.write("Prueba de escritura exitosa.")
    except Exception as e:
        print(f"Error al escribir en el disco: {e}")

# Endpoint para descargar el archivo de base de datos
@app.get("/download/palabras_clave.db")
async def download_file():
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
    return FileResponse(DB_PATH, media_type="application/octet-stream", filename="palabras_clave.db")

# Endpoint para subir el archivo de base de datos
@app.post("/upload_file")
async def upload_file(file: UploadFile = File(...)):
    try:
        with open(DB_PATH, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return {"message": "Archivo subido exitosamente.", "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir el archivo: {str(e)}")

# Formulario para subir archivo
@app.get("/upload_form", response_class=HTMLResponse)
async def upload_form():
    return """
    <!doctype html>
    <html>
    <head>
        <title>Subir palabras_clave.db</title>
    </head>
    <body>
        <h1>Subir un nuevo archivo palabras_clave.db</h1>
        <form action="/upload_file" method="post" enctype="multipart/form-data">
            <input type="file" name="file">
            <button type="submit">Subir</button>
        </form>
    </body>
    </html>
    """

# Clase para solicitudes del usuario
class UserInput(BaseModel):
    mensaje: str
    user_id: str

# Gestión de sesiones activas
user_sessions = {}
SESSION_TIMEOUT = 30  # Tiempo de inactividad en segundos
MAX_INTERACCIONES = 6  # Máximo de interacciones permitidas

@app.on_event("startup")
def startup_event():
    verificar_escritura_en_disco()
    init_db()
    start_session_cleaner()

# Limpieza de sesiones inactivas
def start_session_cleaner():
    def cleaner():
        while True:
            current_time = time.time()
            inactive_users = [
                user_id for user_id, data in user_sessions.items()
                if current_time - data["ultima_interaccion"] > SESSION_TIMEOUT
            ]
            for user_id in inactive_users:
                user_sessions.pop(user_id, None)
            time.sleep(60)

    thread = threading.Thread(target=cleaner, daemon=True)
    thread.start()

# Endpoint inicial
@app.get("/")
def read_root():
    return {"message": "Bienvenido al asistente"}

# Endpoint para interacción con el asistente
@app.post("/asistente")
async def asistente(input_data: UserInput):
    user_id = input_data.user_id
    mensaje_usuario = input_data.mensaje.strip().lower()

    if not mensaje_usuario:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "contador_interacciones": 0,
            "ultima_interaccion": time.time(),
            "sintomas": [],
            "bloqueado": False
        }

    session = user_sessions[user_id]
    session["ultima_interaccion"] = time.time()

    if session["bloqueado"]:
        return {"respuesta": "Has alcanzado el límite de interacciones. Escribe 'reiniciar' para una nueva conversación."}

    if mensaje_usuario == "reiniciar":
        user_sessions[user_id] = {
            "contador_interacciones": 0,
            "ultima_interaccion": time.time(),
            "sintomas": [],
            "bloqueado": False
        }
        return {"respuesta": "La conversación ha sido reiniciada. Empezá de nuevo cuando quieras."}

    session["contador_interacciones"] += 1

    if session["contador_interacciones"] > MAX_INTERACCIONES:
        session["bloqueado"] = True
        return {"respuesta": "Has alcanzado el límite de interacciones. Escribe 'reiniciar' para empezar otra vez."}

    sintomas_usuario = mensaje_usuario.split()
    session["sintomas"].extend(sintomas_usuario)

    if session["contador_interacciones"] == 5:
        categorias_detectadas = obtener_categorias(session["sintomas"])
        sintomas_unicos = set(session["sintomas"])
        categorias_texto = ", ".join(categorias_detectadas)

        return {
            "respuesta": (
                f"Tus síntomas de {', '.join(sintomas_unicos)} pueden estar relacionados con: {categorias_texto}. "
                "Considerá contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186."
            )
        }

    registrar_palabras_clave_limpiadas(mensaje_usuario)
    respuesta = await interactuar_con_openai(mensaje_usuario)
    return {"respuesta": respuesta}

# Interacción con OpenAI
async def interactuar_con_openai(mensaje_usuario: str) -> str:
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres un asistente conversacional profesional y empático."},
                {"role": "user", "content": mensaje_usuario}
            ],
            max_tokens=200,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error al interactuar con OpenAI: {e}")
        return "Lo siento, ocurrió un problema al procesar tu mensaje. Intenta nuevamente más tarde."
