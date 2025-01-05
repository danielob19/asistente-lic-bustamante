import os
import time
import threading
import psycopg2
import openai
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Configuración de la clave de API de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("OPENAI_API_KEY no está configurada en las variables de entorno.")

# Configuración de la URL de la base de datos PostgreSQL
DATABASE_URL = "postgresql://my_postgres_db_oahe_user:AItPOENiOHIGPNva0eiCT0kK1od4UhZf@dpg-ctqqj0bqf0us73f4ar1g-a/my_postgres_db_oahe"

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

# Configuración de la base de datos PostgreSQL
def init_db():
    """
    Inicializa la base de datos creando las tablas necesarias.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS interacciones (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                consulta TEXT NOT NULL,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")

# Generación de respuestas con OpenAI
def generar_respuesta_con_openai(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.6
        )
        content = response.choices[0].message['content'].strip()
        if content:
            return content
        else:
            return "Lo siento, no pude procesar tu solicitud. ¿Podrías intentar reformular tu mensaje?"
    except Exception as e:
        print(f"Error al generar respuesta con OpenAI: {e}")
        return "Lo siento, hubo un problema al procesar tu solicitud. Por favor, intenta nuevamente."

# Clase para solicitudes del usuario
class UserInput(BaseModel):
    mensaje: str
    user_id: str

# Gestión de sesiones (en memoria)
user_sessions = {}
SESSION_TIMEOUT = 60  # Tiempo en segundos para limpiar sesiones inactivas

@app.on_event("startup")
def startup_event():
    init_db()
    start_session_cleaner()

def start_session_cleaner():
    def cleaner():
        while True:
            current_time = time.time()
            inactive_users = [
                user_id for user_id, session in user_sessions.items()
                if current_time - session["ultima_interaccion"] > SESSION_TIMEOUT
            ]
            for user_id in inactive_users:
                del user_sessions[user_id]
            time.sleep(30)
    thread = threading.Thread(target=cleaner, daemon=True)
    thread.start()

@app.post("/asistente")
async def asistente(input_data: UserInput):
    try:
        user_id = input_data.user_id
        mensaje_usuario = input_data.mensaje.strip()

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

        contador = user_sessions[user_id]["contador_interacciones"]

        if contador >= 2 and contador < 6:
            prompt_emocional = f"Analiza el siguiente mensaje para detectar el estado emocional implícito y formula una pregunta empática relacionada con su estado emocional: '{mensaje_usuario}'"
            respuesta_emocional = generar_respuesta_con_openai(prompt_emocional)
            if "no pude procesar" in respuesta_emocional.lower():
                respuesta_emocional = "Parece que estás pasando por un momento difícil. ¿Te gustaría contarme más sobre cómo te sientes?"
            return {"respuesta": respuesta_emocional}

        if contador == 6:
            mensajes = user_sessions[user_id]["mensajes"]
            prompt_analisis = "\\n".join(mensajes)
            prompt_final = f"Con base en las siguientes interacciones, analiza el estado emocional general y proporciona una respuesta profesional: {prompt_analisis}"
            respuesta_final = generar_respuesta_con_openai(prompt_final)
            user_sessions[user_id]["mensajes"].clear()
            return {"respuesta": respuesta_final}

        return {"respuesta": "Gracias por compartir. ¿Hay algo más que quieras decirme?"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

