from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI()

class UserInput(BaseModel):
    mensaje: str

@app.get("/")
def read_root():
    return {"message": "Bienvenido al asistente"}

@app.post("/asistente")
async def asistente(input_data: UserInput):
    try:
        mensaje_usuario = input_data.mensaje.strip()
        if not mensaje_usuario:
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": mensaje_usuario}],
            max_tokens=100
        )
        return {"respuesta": response.choices[0].message.content.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
