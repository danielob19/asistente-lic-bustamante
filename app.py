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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ruta para la base de datos
DB_PATH = "/var/data/palabras_clave.db"
PRUEBA_PATH = "/var/data/prueba_escritura.txt"

if not os.path.exists("/var/data"):
    os.makedirs("/var/data")
    print("Directorio creado: /var/data")

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

# Obtener síntomas existentes
def obtener_sintomas():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT sintoma, cuadro FROM palabras_clave")
        sintomas = cursor.fetchall()
        conn.close()
        return sintomas
    except sqlite3.Error as e:
        print(f"Error al obtener síntomas: {e}")
        return []

# Registrar síntoma nuevo
def registrar_sintoma(sintoma: str, cuadro: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO palabras_clave (sintoma, cuadro) VALUES (?, ?)", (sintoma, cuadro))
        if cursor.rowcount > 0:
            print(f"Síntoma registrado: {sintoma}")
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"Error al registrar síntoma: {e}")

# Generación de respuestas con OpenAI
def generar_respuesta_con_openai(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.7
        )
        respuesta = response.choices[0].message['content'].strip()
        return respuesta
    except Exception as e:
        print(f"Error al generar respuesta con OpenAI: {e}")
        return ""

# Análisis de texto del usuario
def analizar_texto(mensajes_usuario):
    """
    Analiza los mensajes del usuario para detectar coincidencias con los síntomas almacenados
    y usa OpenAI para detectar nuevos estados emocionales si no hay suficientes coincidencias.
    """
    saludos_comunes = {"hola", "buenos", "buenas", "saludos", "qué", "tal", "hey", "hola!"}
    palabras_irrelevantes = {"un", "una", "el", "la", "es", "estoy", "siento", "también", "que", "de", "en", "por", "a", "me", "mi", "tengo", "muy", "poco"}

    sintomas_existentes = obtener_sintomas()
    if not sintomas_existentes:
        return "No se encontraron síntomas para analizar."

    keyword_to_cuadro = {sintoma.lower(): cuadro for sintoma, cuadro in sintomas_existentes}
    coincidencias = []
    sintomas_detectados = []

    # Procesar cada mensaje del usuario
    for mensaje in mensajes_usuario:
        user_words = mensaje.lower().split()
        user_words = [palabra for palabra in user_words if palabra not in saludos_comunes and palabra not in palabras_irrelevantes]

        for palabra in user_words:
            if palabra in keyword_to_cuadro:
                coincidencias.append(keyword_to_cuadro[palabra])
                sintomas_detectados.append(palabra)

    # Si no hay suficientes coincidencias, usar OpenAI
    if len(coincidencias) < 2:
        texto_usuario = " ".join(mensajes_usuario)
        prompt = (
            f"Analiza este mensaje para detectar emociones o síntomas psicológicos:\n\n"
            f"{texto_usuario}\n\n"
            "Responde con una lista de emociones separadas por comas."
        )
        try:
            emociones_detectadas = generar_respuesta_con_openai(prompt).split(",")
            for emocion in emociones_detectadas:
                emocion = emocion.strip().lower()
                if emocion and emocion not in keyword_to_cuadro:
                    registrar_sintoma(emocion, "detectado por IA")
                    keyword_to_cuadro[emocion] = "detectado por IA"
                    coincidencias.append("detectado por IA")
                    sintomas_detectados.append(emocion)
        except Exception as e:
            print(f"Error al usar OpenAI: {e}")
            return "Error al analizar el texto con IA."

    if not coincidencias:
        return "No se encontraron coincidencias para determinar un cuadro psicológico."

    category_counts = Counter(coincidencias)
    cuadro_probable, frecuencia = category_counts.most_common(1)[0]
    probabilidad = (frecuencia / len(coincidencias)) * 100

    return (
        f"En base a los síntomas detectados ({', '.join(set(sintomas_detectados))}), es posible que se trate de {cuadro_probable}. "
        "Se recomienda consultar a un profesional especializado para mayor claridad."
    )

# Clase para solicitudes del usuario
class UserInput(BaseModel):
    mensaje: str
    user_id: str

# Gestión de sesiones (en memoria)
user_sessions = {}
SESSION_TIMEOUT = 300

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

# Endpoint principal para interacción
@app.post("/asistente")
async def asistente(input_data: UserInput):
    try:
        user_id = input_data.user_id
        mensaje_usuario = input_data.mensaje.strip().lower()

        if not mensaje_usuario:
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

        if user_id not in user_sessions:
            user_sessions[user_id] = {
                "ultima_interaccion": time.time(),
                "mensajes": []
            }

        user_sessions[user_id]["ultima_interaccion"] = time.time()
        user_sessions[user_id]["mensajes"].append(mensaje_usuario)

        if len(user_sessions[user_id]["mensajes"]) == 5:
            respuesta = analizar_texto(user_sessions[user_id]["mensajes"])
            mensajes = " ".join(user_sessions[user_id]["mensajes"])
            user_sessions[user_id]["mensajes"] = []
            return {
                "respuesta": (
                    f"Hemos detectado lo siguiente: {respuesta}. Aunque no todos los síntomas detectados están relacionados con el cuadro identificado, indican la necesidad de apoyo profesional. "
                    f"Por favor, contáctame al WhatsApp +54 911 3310-1186 para una consulta más detallada."
                )
            }

        return {"respuesta": "Gracias por tu mensaje. ¿Hay algo más que quieras compartir?"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
