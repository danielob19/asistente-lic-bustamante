import os
import re
import time
import threading
import sqlite3
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
import shutil

# Configuración de la clave de API de OpenAI
import openai

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
    "o", "u", "porque", "como", "tal", "poco", "tengo", "te", "se", "soy", "hace", "ya", "verdad", "sé"
}

# Función para limpiar mensajes y filtrar palabras irrelevantes
def limpiar_mensaje(mensaje_usuario: str) -> list:
    """
    Limpia el mensaje del usuario eliminando palabras irrelevantes y caracteres especiales.
    """
    palabras_usuario = re.findall(r'\b\w+\b', mensaje_usuario.lower())
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
    """
    Registra una palabra clave en la base de datos si no está en la lista de palabras irrelevantes.
    """
    if palabra in PALABRAS_IRRELEVANTES:
        return

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
    """
    Detecta palabras clave relevantes en el mensaje del usuario y las registra en la base de datos.
    """
    palabras_clave = limpiar_mensaje(mensaje_usuario)
    for palabra in palabras_clave:
        registrar_palabra_clave(palabra, "categoría pendiente")

# Función para obtener categorías asociadas
def obtener_categorias(sintomas):
    """
    Busca en la base de datos las categorías asociadas a los síntomas proporcionados.
    """
    categorias = set()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        for sintoma in sintomas:
            cursor.execute("SELECT categoria FROM palabras_clave WHERE palabra = ?", (sintoma,))
            resultados = cursor.fetchall()
            for resultado in resultados:
                categorias.add(resultado[0])
        conn.close()
    except Exception as e:
        print(f"Error al obtener categorías: {e}")
    return list(categorias)

# Clase para solicitudes del usuario
class UserInput(BaseModel):
    mensaje: str
    user_id: str

# Gestión de sesiones activas
user_sessions = {}
SESSION_TIMEOUT = 300  # Tiempo de inactividad en segundos
MAX_INTERACCIONES = 6  # Máximo de interacciones permitidas

@app.on_event("startup")
def startup_event():
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

# Endpoint para interacción con el asistente
@app.post("/asistente")
async def asistente(input_data: UserInput):
    """
    Procesa un mensaje del usuario y responde en el flujo de diálogo.
    """
    user_id = input_data.user_id
    mensaje_usuario = input_data.mensaje.strip().lower()

    if not mensaje_usuario:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

    # Limpia y registra palabras clave
    palabras_clave = limpiar_mensaje(mensaje_usuario)
    registrar_palabras_clave_limpiadas(mensaje_usuario)

    # Inicializa la sesión del usuario si no existe
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "contador_interacciones": 0,
            "ultima_interaccion": time.time(),
            "sintomas": [],
        }

    session = user_sessions[user_id]
    session["ultima_interaccion"] = time.time()
    session["contador_interacciones"] += 1

    # Guarda síntomas detectados
    session["sintomas"].extend(palabras_clave)

    # Termina el flujo en la interacción 6
    if session["contador_interacciones"] == MAX_INTERACCIONES:
        categorias_detectadas = obtener_categorias(session["sintomas"])
        if not categorias_detectadas:
            categorias_detectadas = ["categoría pendiente"]

        sintomas_unicos = list(set(session["sintomas"]))
        return {
            "respuesta": (
                f"Entendido. Detecté síntomas relacionados con: {', '.join(sintomas_unicos)}. "
                f"Esto podría estar asociado con: {', '.join(categorias_detectadas)}. "
                "Si lo consideras necesario, contacta al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186. "
                "Gracias por compartir tu situación, espero haberte ayudado."
            )
        }

    # Generar una respuesta normal con OpenAI para interacciones previas
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
