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
from collections import Counter

# Configuración de la clave de API de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("OPENAI_API_KEY no está configurada en las variables de entorno.")

# Inicialización de FastAPI
app = FastAPI()

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cambiar "*" a una lista de dominios específicos si es necesario
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ruta para la base de datos
DB_PATH = "/var/data/palabras_clave.db"  # Cambia esta ruta según el disco persistente
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

# Obtener palabras clave existentes
def obtener_palabras_clave():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT palabra, categoria FROM palabras_clave")
        palabras = cursor.fetchall()
        conn.close()
        return palabras
    except Exception as e:
        print(f"Error al obtener palabras clave: {e}")
        return []

# Análisis de texto del usuario
def analizar_texto(mensajes_usuario):
    palabras_clave = obtener_palabras_clave()
    if not palabras_clave:
        return "No se encontraron palabras clave para analizar."

    keyword_to_category = {palabra.lower(): categoria for palabra, categoria in palabras_clave}
    coincidencias = []
    palabras_detectadas = []

    for mensaje in mensajes_usuario:
        user_words = mensaje.lower().split()
        for palabra in user_words:
            if palabra in keyword_to_category:
                coincidencias.append(keyword_to_category[palabra])
                palabras_detectadas.append(palabra)

    if len(coincidencias) < 2:
        return "No se encontraron suficientes coincidencias para determinar un cuadro psicológico."

    category_counts = Counter(coincidencias)
    cuadro_probable, frecuencia = category_counts.most_common(1)[0]
    probabilidad = (frecuencia / len(coincidencias)) * 100

    return (
        f"En base a los síntomas referidos ({', '.join(set(palabras_detectadas))}), pareciera tratarse de una afección o cuadro relacionado con {cuadro_probable}. "
        f"Por lo que te sugiero contactar al Lic. Daniel O. Bustamante, un profesional especializado, al WhatsApp +54 911 3310-1186. "
        f"Él podrá ofrecerte una evaluación y un apoyo más completo."
    )

# Verificar escritura en disco
def verificar_escritura_en_disco():
    try:
        with open(PRUEBA_PATH, "w") as archivo:
            archivo.write("Prueba de escritura exitosa.")
    except Exception as e:
        print(f"Error al escribir en el disco: {e}")

# Clase para solicitudes del usuario
class UserInput(BaseModel):
    mensaje: str
    user_id: str

# Gestión de sesiones (en memoria)
user_sessions = {}
SESSION_TIMEOUT = 60  # Tiempo de inactividad en segundos

@app.on_event("startup")
def startup_event():
    verificar_escritura_en_disco()  # Prueba de escritura
    init_db()  # Inicializar base de datos
    start_session_cleaner()  # Iniciar limpieza de sesiones

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

# Endpoint principal para interacción con el asistente
@app.post("/asistente")
async def asistente(input_data: UserInput):
    try:
        user_id = input_data.user_id
        mensaje_usuario = input_data.mensaje.strip().lower()

        if not mensaje_usuario:
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

        # Inicializar sesión si no existe
        if user_id not in user_sessions:
            user_sessions[user_id] = {
                "contador_interacciones": 0,
                "ultima_interaccion": time.time(),
                "mensajes": []
            }

        user_sessions[user_id]["ultima_interaccion"] = time.time()
        user_sessions[user_id]["contador_interacciones"] += 1
        user_sessions[user_id]["mensajes"].append(mensaje_usuario)
        interacciones = user_sessions[user_id]["contador_interacciones"]

        # Reinicio de conversación
        if mensaje_usuario == "reiniciar":
            if user_id in user_sessions:
                user_sessions.pop(user_id)
                return {"respuesta": "La conversación ha sido reiniciada. Empezá de nuevo cuando quieras."}
            else:
                return {"respuesta": "No se encontró una sesión activa. Empezá una nueva conversación cuando quieras."}

        # Respuesta en la interacción 6
        if interacciones > 5:
            return {
                "respuesta": (
                    "Si bien debo concluir nuestra conversación, no obstante te sugiero contactar al Lic. Daniel O. Bustamante, un profesional especializado, "
                    "al WhatsApp +54 911 3310-1186. Un saludo."
                )
            }

        # Análisis en la interacción 5
        if interacciones == 5:
            mensajes = user_sessions[user_id]["mensajes"]
            respuesta_analisis = analizar_texto(mensajes)
            user_sessions[user_id]["mensajes"].clear()  # Limpiar mensajes tras el análisis
            return {"respuesta": respuesta_analisis}

        # Continuar recopilando información
        return {"respuesta": "Estoy recopilando información, por favor continúa describiendo tus síntomas."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
