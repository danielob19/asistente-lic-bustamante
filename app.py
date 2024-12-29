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
                sintoma TEXT UNIQUE NOT NULL,
                cuadro TEXT NOT NULL
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

@app.get("/download/palabras_clave.db")
async def download_file():
    """
    Permite al usuario descargar el archivo de base de datos.
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
    return FileResponse(DB_PATH, media_type="application/octet-stream", filename="palabras_clave.db")

@app.post("/upload_file")
async def upload_file(file: UploadFile = File(...)):
    """
    Permite al usuario subir un nuevo archivo para reemplazar la base de datos existente.
    """
    try:
        with open(DB_PATH, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return {"message": "Archivo subido exitosamente.", "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir el archivo: {str(e)}")

@app.get("/upload_form", response_class=HTMLResponse)
async def upload_form():
    """
    Proporciona un formulario simple para que el usuario pueda subir el archivo de base de datos.
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

def registrar_sintoma(sintoma: str, cuadro: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO palabras_clave (sintoma, cuadro) VALUES (?, ?)", (sintoma, cuadro))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error al registrar síntoma: {e}")

def obtener_sintomas():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT sintoma, cuadro FROM palabras_clave")
        sintomas = cursor.fetchall()
        conn.close()
        return sintomas
    except Exception as e:
        print(f"Error al obtener síntomas: {e}")
        return []

palabras_irrelevantes = {
    "un", "una", "el", "la", "es", "son", "estoy", "siento", "me siento", "que", "de", "en",
    "por", "a", "me", "mi", "tengo", "muy", "poco", "tambien", "si", "supuesto", "frecuentes", "verdad", "sé", "hoy",
    "quiero", "mucho", "hola", "no", "entiendo", "buenas", "noches", "soy", "daniel", "mi", "numero", "telefono", "opinas", "?"
}

def analizar_texto(mensajes_usuario):
    sintomas_existentes = obtener_sintomas()
    if not sintomas_existentes:
        return "No se encontraron síntomas para analizar."

    keyword_to_cuadro = {sintoma.lower(): cuadro for sintoma, cuadro in sintomas_existentes}
    coincidencias = []
    sintomas_detectados = []

    for mensaje in mensajes_usuario:
        user_words = mensaje.lower().split()
        user_words = [palabra for palabra in user_words if palabra not in palabras_irrelevantes]

        for palabra in user_words:
            if palabra in keyword_to_cuadro:
                coincidencias.append(keyword_to_cuadro[palabra])
                sintomas_detectados.append(palabra)

    texto_usuario = " ".join(mensajes_usuario)
    emociones_detectadas = []

    if len(coincidencias) < 2:
        prompt = (
            f"Analiza el siguiente mensaje y detecta emociones o estados psicológicos implícitos:\n\n"
            f"{texto_usuario}\n\n"
            "Responde con una lista de emociones o estados emocionales separados por comas."
        )
        try:
            respuesta_openai = generar_respuesta_con_openai(prompt)
            emociones_detectadas = [e.strip().lower() for e in respuesta_openai.split(",")]
            for emocion in emociones_detectadas:
                if emocion and emocion not in keyword_to_cuadro:
                    registrar_sintoma(emocion, "estado emocional detectado por IA")
                    coincidencias.append("estado emocional detectado por IA")
                    sintomas_detectados.append(emocion)
        except Exception as e:
            print(f"Error al usar OpenAI para detectar emociones: {e}")

    if not coincidencias:
        return "No se encontraron suficientes coincidencias para determinar un cuadro psicológico."

    category_counts = Counter(coincidencias)
    cuadro_probable, frecuencia = category_counts.most_common(1)[0]
    probabilidad = (frecuencia / len(coincidencias)) * 100

    emociones_mencionadas = ", ".join(set(emociones_detectadas))

    return (
        f"Con base en los síntomas detectados ({', '.join(set(sintomas_detectados))}), parece estar relacionado con un {cuadro_probable} ({probabilidad:.2f}% de certeza)."
        f" Emociones adicionales detectadas: {emociones_mencionadas}."
        " Te recomiendo contactar a un profesional, como el Lic. Daniel O. Bustamante, al WhatsApp +54 911 3310-1186, para una evaluación más detallada."
    )

def generar_respuesta_con_openai(prompt):
    try:
        prompt = f"{prompt}\nResponde de manera profesional, pero directa y objetiva."
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.6
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        print(f"Error al generar respuesta con OpenAI: {e}")
        return "Lo siento, hubo un problema al generar una respuesta. Por favor, intenta nuevamente."

class UserInput(BaseModel):
    mensaje: str
    user_id: str

user_sessions = {}
SESSION_TIMEOUT = 60

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
                    "Debo concluir nuestra conversación. Te sugiero contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 para una consulta profesional."
                )
            }

        if interacciones == 5:
            mensajes = user_sessions[user_id]["mensajes"]
            respuesta_analisis = analizar_texto(mensajes)
            user_sessions[user_id]["mensajes"].clear()
            return {"respuesta": respuesta_analisis}

        prompt = f"Un usuario dice: '{mensaje_usuario}'. Responde de manera profesional y empática."
        respuesta_ai = generar_respuesta_con_openai(prompt)
        return {"respuesta": respuesta_ai}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
