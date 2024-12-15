import os
import re
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

# Palabras irrelevantes
PALABRAS_IRRELEVANTES = {
    "mal", "me", "hola", "estoy", "muy", "siento", "es", "a", "de", "que", "en", "con", "por", "si", "no", 
    "un", "una", "el", "la", "los", "las", "al", "del", "lo", "mi", "mis", "tu", "tus", "su", "sus", "y", 
    "o", "u", "porque", "como", "tal", "poco", "tengo", "te", "se", "soy", "hace", "ya"
}

# Función para limpiar mensajes y filtrar palabras irrelevantes
def limpiar_mensaje(mensaje_usuario: str) -> list:
    """
    Limpia el mensaje del usuario eliminando palabras irrelevantes y caracteres especiales.
    """
    # Convertir a minúsculas y dividir en palabras
    palabras_usuario = re.findall(r'\b\w+\b', mensaje_usuario.lower())

    # Filtrar palabras irrelevantes
    palabras_clave = [
        palabra for palabra in palabras_usuario if palabra not in PALABRAS_IRRELEVANTES
    ]
    
    return palabras_clave

# Inicialización de la base de datos SQLite
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
        conn.commit()
        conn.close()
        print(f"Base de datos creada o abierta en: {DB_PATH}")
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")

# Registrar palabra clave nueva
def registrar_palabra_clave(palabra: str, categoria: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO palabras_clave (palabra, categoria) VALUES (?, ?)", (palabra, categoria))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error al registrar palabra clave: {e}")

# Detectar y registrar nuevas palabras clave
def registrar_palabras_clave_limpiadas(mensaje_usuario: str):
    palabras_clave = limpiar_mensaje(mensaje_usuario)

    if not palabras_clave:
        print("No se encontraron palabras clave relevantes en el mensaje.")
        return

    for palabra in palabras_clave:
        registrar_palabra_clave(palabra, "categoría pendiente")

# Obtener categorías asociadas a los síntomas
def obtener_categorias(sintomas):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        categorias = set()
        for sintoma in sintomas:
            cursor.execute("SELECT categoria FROM palabras_clave WHERE palabra LIKE ?", (f"%{sintoma}%",))
            resultados = cursor.fetchall()
            for resultado in resultados:
                categorias.add(resultado[0])
        conn.close()
        return list(categorias)
    except Exception as e:
        print(f"Error al obtener categorías: {e}")
        return []

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

# Endpoint para descargar el archivo de base de datos
@app.get("/download/palabras_clave.db")
async def download_database():
    """
    Descarga la base de datos `palabras_clave.db`.
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
    return FileResponse(DB_PATH, media_type="application/octet-stream", filename="palabras_clave.db")

# Endpoint para subir un archivo y reemplazar la base de datos
@app.post("/upload_file")
async def upload_database(file: UploadFile = File(...)):
    """
    Permite subir un archivo y reemplazar la base de datos actual.
    """
    try:
        with open(DB_PATH, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return {"message": "Archivo subido exitosamente.", "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir el archivo: {str(e)}")

# Formulario HTML para subir la base de datos
@app.get("/upload_form", response_class=HTMLResponse)
async def upload_form():
    """
    Devuelve un formulario HTML para cargar un nuevo archivo de base de datos desde el navegador.
    """
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

    # Limpiar y registrar palabras clave
    palabras_clave_limpiadas = limpiar_mensaje(mensaje_usuario)
    session["sintomas"].extend(palabras_clave_limpiadas)

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
