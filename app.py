import os
import time
import threading
import sqlite3
import openai
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from collections import Counter

# Configuración de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("OPENAI_API_KEY no está configurada en las variables de entorno.")

# Inicialización de FastAPI
app = FastAPI()

# Ruta para la base de datos
DB_PATH = "/var/data/palabras_clave.db"

# Configuración de la base de datos SQLite
def init_db():
    try:
        if not os.path.exists(os.path.dirname(DB_PATH)):
            os.makedirs(os.path.dirname(DB_PATH))
        if not os.path.exists(DB_PATH):
            print(f"Creando base de datos en: {DB_PATH}")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS palabras_clave (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                palabra TEXT UNIQUE NOT NULL,
                categoria TEXT NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()
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

# Análisis del texto
def analizar_texto(mensajes_usuario):
    saludos_comunes = {"hola", "buenos", "buenas", "saludos", "qué", "tal", "hey", "hola!"}
    palabras_clave = obtener_palabras_clave()
    if not palabras_clave:
        return "No se encontraron palabras clave en la base de datos."

    keyword_to_category = {palabra.lower(): categoria for palabra, categoria in palabras_clave}
    coincidencias = []
    palabras_detectadas = []
    palabras_nuevas = []

    for mensaje in mensajes_usuario:
        user_words = mensaje.lower().split()
        user_words = [palabra for palabra in user_words if palabra not in saludos_comunes]
        for palabra in user_words:
            if palabra in keyword_to_category:
                coincidencias.append(keyword_to_category[palabra])
                palabras_detectadas.append(palabra)
            else:
                palabras_nuevas.append(palabra)

    for nueva_palabra in set(palabras_nuevas):
        try:
            respuesta = openai.Completion.create(
                engine="text-davinci-003",
                prompt=f"¿La palabra '{nueva_palabra}' está relacionada con emociones humanas como depresión, ansiedad, estrés, etc.?",
                max_tokens=50
            )
            if "sí" in respuesta.choices[0].text.lower():
                registrar_palabra_clave(nueva_palabra, "pendiente")
        except Exception as e:
            print(f"Error al registrar nueva palabra: {e}")

    if len(coincidencias) >= 2:
        category_counts = Counter(coincidencias)
        cuadro_probable, _ = category_counts.most_common(1)[0]
        return (
            f"En base a los síntomas referidos ({', '.join(set(palabras_detectadas))}), pareciera tratarse de un {cuadro_probable}."
        )

    return "No se encontraron suficientes coincidencias para determinar un cuadro psicológico."

class UserInput(BaseModel):
    mensaje: str
    user_id: str

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

@app.post("/asistente")
async def asistente(input_data: UserInput):
    try:
        user_id = input_data.user_id
        mensaje_usuario = input_data.mensaje.strip().lower()

        if not mensaje_usuario:
            return {"respuesta": "Por favor, dime cómo te sientes o qué te preocupa."}

        if user_id not in user_sessions:
            user_sessions[user_id] = {
                "contador_interacciones": 0,
                "ultima_interaccion": time.time(),
                "mensajes": []
            }
            if mensaje_usuario in {"hola", "buenos días", "buenas tardes"}:
                return {"respuesta": "¡Hola! ¿Cómo te sientes hoy?"}

        user_sessions[user_id]["ultima_interaccion"] = time.time()
        user_sessions[user_id]["contador_interacciones"] += 1
        user_sessions[user_id]["mensajes"].append(mensaje_usuario)

        interacciones = user_sessions[user_id]["contador_interacciones"]

        if interacciones == 5:
            mensajes = user_sessions[user_id]["mensajes"]
            respuesta_analisis = analizar_texto(mensajes)
            user_sessions[user_id]["mensajes"].clear()
            return {"respuesta": respuesta_analisis}

        if interacciones == 6:
            user_sessions.pop(user_id, None)
            return {
                "respuesta": (
                    "Gracias por compartir conmigo. Te recomiendo contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186. Él podrá ayudarte de manera profesional."
                )
            }

        return {"respuesta": "Estoy recopilando información, por favor continúa describiendo tus síntomas."}

    except openai.error.OpenAIError as e:
        print(f"Error al conectar con OpenAI: {e}")
        return {"respuesta": "Lo siento, no puedo procesar tu solicitud en este momento debido a un problema técnico con OpenAI."}

    except sqlite3.Error as e:
        print(f"Error con la base de datos: {e}")
        return {"respuesta": "Lo siento, ocurrió un problema técnico con nuestra base de datos. Inténtalo más tarde."}

    except Exception as e:
        print(f"Error en el asistente: {e}")
        return {"respuesta": f"Lo siento, ocurrió un error técnico: {str(e)}"}
