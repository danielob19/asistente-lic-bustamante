import time
import threading
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai
import json
import os

# Configuración de la clave de API
openai.api_key = os.getenv("OPENAI_API_KEY")

# Inicialización de FastAPI
app = FastAPI()

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cambia "*" por una lista de dominios permitidos si lo necesitas
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simulación de sesiones (almacenamiento en memoria)
user_sessions = {}
SESSION_TIMEOUT = 60  # Tiempo de inactividad permitido en segundos

class UserInput(BaseModel):
    mensaje: str
    user_id: str

@app.get("/")
def read_root():
    return {"message": "Bienvenido al asistente"}

@app.on_event("startup")
def start_session_cleaner():
    """Inicia un thread para limpiar sesiones inactivas."""
    def cleaner():
        while True:
            current_time = time.time()
            inactive_users = [
                user_id for user_id, data in user_sessions.items()
                if current_time - data["ultima_interaccion"] > SESSION_TIMEOUT
            ]
            for user_id in inactive_users:
                user_sessions.pop(user_id, None)  # Elimina sesiones inactivas
            time.sleep(60)  # Ejecuta la limpieza cada 60 segundos

    thread = threading.Thread(target=cleaner, daemon=True)
    thread.start()

@app.post("/asistente")
async def asistente(input_data: UserInput):
    try:
        user_id = input_data.user_id
        mensaje_usuario = input_data.mensaje.strip()

        if not mensaje_usuario:
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

         # Inicializar sesión si no existe
        if user_id not in user_sessions:
            user_sessions[user_id] = {"contador_interacciones": 0, "ultima_interaccion": time.time()}
        else:
            # Actualizar la marca de tiempo de la última interacción
            user_sessions[user_id]["ultima_interaccion"] = time.time()
            
        user_sessions[user_id]["contador_interacciones"] += 1
        interacciones = user_sessions[user_id]["contador_interacciones"]

        # Manejo específico para "sí"
        if mensaje_usuario == "sí" or mensaje_usuario == "si":
            if user_sessions[user_id]["ultimo_contexto"] == "confirmación":
                return {"respuesta": "Ya confirmaste eso. ¿Hay algo más en lo que pueda ayudarte?"}
            user_sessions[user_id]["ultimo_contexto"] = "confirmación"
            return {"respuesta": "Gracias por confirmar. ¿Hay algo más en lo que pueda ayudarte?"}

        # Actualizar el último contexto basado en el mensaje
        user_sessions[user_id]["ultimo_contexto"] = mensaje_usuario

async def interactuar_con_openai(mensaje_usuario: str) -> str:
    try:
        # Solicitar la respuesta a OpenAI
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres un asistente conversacional profesional y empático."},
                {"role": "user", "content": mensaje_usuario}
            ],
            max_tokens=200,
            temperature=0.7
        )
        respuesta = response.choices[0].message.content.strip()
        return respuesta
    except Exception as e:
        # Manejo de errores
        print(f"Error al comunicarse con OpenAI: {e}")
        return "Lo siento, ocurrió un problema al procesar tu solicitud. Por favor, inténtalo más tarde."

            
         # Reiniciar la conversación si el mensaje es "reiniciar"
        if mensaje_usuario == "reiniciar":
            user_sessions.pop(user_id, None)  # Eliminar la sesión del usuario
            return {"respuesta": "La conversación ha sido reiniciada. Puedes empezar de nuevo."}

        if interacciones >= 6:
            return {
                "respuesta": (
                    "La conversación ha terminado. Igualmente por lo que me comentaste, "
                    "te sugiero nuevamente contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 "
                    "para una evaluación más profunda. Para reiniciar el chat escriba reiniciar"
                )
            }
        
        if interacciones == 5:
            return {
                "respuesta": (
                    "Comprendo perfectamente. Si lo considerás necesario, "
                    "contactá al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 "
                    "para una evaluación más profunda."
                )
            }

        respuesta = await interactuar_con_openai(mensaje_usuario)
        return {"respuesta": respuesta}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

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
        raise HTTPException(status_code=502, detail=f"Error al comunicarse con OpenAI: {str(e)}")
