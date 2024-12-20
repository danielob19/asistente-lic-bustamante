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
    allow_origins=["http://localhost", "https://tu-dominio.com"],  # Restringir a dominios específicos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ruta para la base de datos
DB_PATH = "/var/data/palabras_clave.db"  # Cambia esta ruta según tu entorno
PRUEBA_PATH = "/var/data/prueba_escritura.txt"

# Configuración de la base de datos SQLite
def init_db():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS palabras_clave (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    palabra TEXT UNIQUE NOT NULL,
                    categoria TEXT NOT NULL,
                    sintoma TEXT DEFAULT NULL
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
        print(f"Base de datos creada o abierta en: {DB_PATH}")
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")

# Registrar palabra clave nueva
def registrar_palabra_clave(palabra: str, categoria: str, sintoma: str):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO palabras_clave (palabra, categoria, sintoma) VALUES (?, ?, ?)",
                (palabra, categoria, sintoma)
            )
            conn.commit()
    except sqlite3.IntegrityError:
        print("La palabra clave ya existe en la base de datos.")
    except Exception as e:
        print(f"Error al registrar palabra clave: {e}")

# Obtener palabras clave existentes
def obtener_palabras_clave():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT palabra, categoria, sintoma FROM palabras_clave")
            palabras = cursor.fetchall()
        return palabras
    except Exception as e:
        print(f"Error al obtener palabras clave: {e}")
        return []

# Análisis de texto del usuario
def analizar_texto(mensajes_usuario):
    saludos_comunes = {"hola", "buenos", "buenas", "saludos", "qué", "tal", "hey", "hola!"}

    palabras_clave = obtener_palabras_clave()
    if not palabras_clave:
        return "No se encontraron palabras clave para analizar."

    keyword_to_category = {palabra.lower(): (categoria, sintoma) for palabra, categoria, sintoma in palabras_clave}
    coincidencias = []
    palabras_detectadas = []

    for mensaje in mensajes_usuario:
        user_words = mensaje.lower().split()
        user_words = [palabra for palabra in user_words if palabra not in saludos_comunes]
        for palabra in user_words:
            if palabra in keyword_to_category:
                coincidencias.append(keyword_to_category[palabra][0])
                palabras_detectadas.append(palabra)

    if len(coincidencias) < 2:
        return f"No se encontraron suficientes coincidencias en tus mensajes: {', '.join(set(palabras_detectadas))}."

    category_counts = Counter(coincidencias)
    cuadro_probable, _ = category_counts.most_common(1)[0]

    try:
        prompt = (
            f"He recibido los siguientes síntomas: {', '.join(set(palabras_detectadas))}. "
            f"Parece tratarse de un cuadro relacionado con {cuadro_probable}. "
            "Por favor, genera una respuesta profesional y comprensiva para el usuario."
        )
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            max_tokens=150,
            temperature=0.7
        )
        return response.choices[0].text.strip()
    except Exception as e:
        print(f"Error en la API de OpenAI: {e}")
        return (
            f"En base a los síntomas referidos ({', '.join(set(palabras_detectadas))}), pareciera tratarse de una afección o cuadro relacionado con {cuadro_probable}. "
            f"Por lo que te sugiero contactar a un profesional especializado."
        )

# Clase para registrar una nueva palabra clave
class NuevaPalabra(BaseModel):
    palabra: str
    categoria: str
    sintoma: str

@app.post("/registrar_palabra")
async def registrar_nueva_palabra(data: NuevaPalabra):
    try:
        registrar_palabra_clave(data.palabra.lower(), data.categoria.lower(), data.sintoma.lower())
        return {"mensaje": "Palabra registrada exitosamente."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al registrar palabra: {str(e)}")

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

@app.get("/")
def read_root():
    return {"message": "Bienvenido al asistente"}

@app.get("/download/palabras_clave.db")
async def download_file():
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
    return FileResponse(DB_PATH, media_type="application/octet-stream", filename="palabras_clave.db")

@app.post("/upload_file")
async def upload_file(file: UploadFile = File(...)):
    try:
        backup_path = DB_PATH + ".backup"
        if os.path.exists(DB_PATH):
            shutil.copy(DB_PATH, backup_path)

        with open(DB_PATH, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return {"message": "Archivo subido exitosamente.", "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir el archivo: {str(e)}")

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

@app.post("/asistente")
async def asistente(input_data: UserInput):
    try:
        user_id = input_data.user_id
        mensaje_usuario = input_data.mensaje.strip().lower()

        if not mensaje_usuario:
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

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

        if mensaje_usuario == "reiniciar":
            user_sessions.pop(user_id, None)
            return {"respuesta": "La conversación ha sido reiniciada. Empezá de nuevo cuando quieras."}

        if interacciones > 5:
            return {
                "respuesta": (
                    "Debo concluir nuestra conversación. Por favor, contacta a un profesional especializado."
                )
            }

        if interacciones == 5:
            mensajes = user_sessions[user_id]["mensajes"]
            respuesta_analisis = analizar_texto(mensajes)
            user_sessions[user_id]["mensajes"].clear()
            return {"respuesta": respuesta_analisis}

        return {"respuesta": "Estoy recopilando información, por favor continúa describiendo tus síntomas."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
