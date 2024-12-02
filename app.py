from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import openai
import os

# Configuración de la clave de API
openai.api_key = os.getenv("OPENAI_API_KEY")

# Inicialización de FastAPI
app = FastAPI()

# Simulación de sesiones (almacenamiento en memoria)
user_sessions = {}

class UserInput(BaseModel):
    mensaje: str
    user_id: str

@app.post("/asistente")
async def asistente(input_data: UserInput):
    try:
        user_id = input_data.user_id
        mensaje_usuario = input_data.mensaje.strip()

        if not mensaje_usuario:
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

        # Inicializar sesión del usuario si no existe
        if user_id not in user_sessions:
            user_sessions[user_id] = {"contador_interacciones": 0}
        
        # Incrementar contador de interacciones
        user_sessions[user_id]["contador_interacciones"] += 1
        interacciones = user_sessions[user_id]["contador_interacciones"]

        # Si es la tercera interacción, sugerir contacto profesional
        if interacciones >= 3:
            # Eliminar la sesión del usuario
            user_sessions.pop(user_id, None)
            return {
                "respuesta": (
                    "Gracias por compartir cómo te sentís. Si lo considerás necesario, "
                    "contactá al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 "
                    "para una evaluación más profunda."
                )
            }

        # Generar respuesta usando OpenAI
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
