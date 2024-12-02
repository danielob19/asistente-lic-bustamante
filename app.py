from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import openai
import os

# Configuración de clave de API
openai.api_key = os.getenv("OPENAI_API_KEY")

# Inicialización de FastAPI
app = FastAPI()

class UserInput(BaseModel):
    mensaje: str

@app.post("/asistente")
async def asistente(input_data: UserInput):
    try:
        mensaje_usuario = input_data.mensaje.strip()
        if not mensaje_usuario:
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")
        respuesta = await interactuar_con_openai(mensaje_usuario)
        return {"respuesta": respuesta}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

async def interactuar_con_openai(mensaje_usuario: str) -> str:
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres un asistente útil y amable."},
                {"role": "user", "content": mensaje_usuario}
            ],
            max_tokens=200,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al comunicarse con OpenAI: {str(e)}")
