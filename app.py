from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import openai
import os

# Configuración de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Configuración de FastAPI
app = FastAPI()

# Permitir solicitudes CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simulación de sesiones (almacenamiento en memoria)
user_sessions = {}

# Modelo de entrada
class UserInput(BaseModel):
    mensaje: str
    user_id: str

@app.post("/asistente")
async def asistente(input_data: UserInput):
    try:
        user_id = input_data.user_id
        mensaje_usuario = input_data.mensaje.strip()

        if not mensaje_usuario:
            raise HTTPException(status_code=400, detail="Por favor, proporciona un mensaje válido.")

        # Inicializar sesión del usuario si no existe
        if user_id not in user_sessions:
            user_sessions[user_id] = {"contador_interacciones": 0, "respuestas_usuario": []}
            print(f"Inicializando sesión para el usuario: {user_id}")

        # Incrementar contador y registrar interacción
        session = user_sessions[user_id]
        session["contador_interacciones"] += 1
        session["respuestas_usuario"].append(mensaje_usuario)

        # Depurar: Mostrar estado actual de la sesión
        print(f"Estado actual de la sesión del usuario {user_id}: {session}")

        # Verificar si es la tercera interacción
        if session["contador_interacciones"] >= 3:
            respuesta_final = (
                "Para una evaluación más profunda de tu malestar, te recomiendo solicitar un turno de consulta "
                "con el Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186, siempre que sea de tu interés "
                "resolver tu afección psicológica y emocional."
            )
            # Limpiar sesión después de la recomendación
            user_sessions.pop(user_id, None)
            return JSONResponse(content={"respuesta": respuesta_final})

        # Generar respuesta de OpenAI
        respuesta = await interactuar_con_openai(mensaje_usuario)
        return JSONResponse(content={"respuesta": respuesta})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def interactuar_con_openai(mensaje_usuario):
    try:
        print(f"Enviando solicitud a OpenAI con el mensaje: {mensaje_usuario}")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres un asistente conversacional profesional y empático."},
                {"role": "user", "content": mensaje_usuario}
            ],
            max_tokens=200,
            temperature=0.7
        )
        print(f"Respuesta de OpenAI: {response}")
        return response['choices'][0]['message']['content'].strip()
    except openai.error.AuthenticationError:
        print("Error: Clave de API de OpenAI no válida o no configurada.")
        return "Error: Clave de API inválida."
    except openai.error.RateLimitError:
        print("Error: Límite de solicitudes alcanzado en OpenAI.")
        return "Error: Se alcanzó el límite de solicitudes. Inténtalo más tarde."
    except openai.error.OpenAIError as e:
        print(f"Error en OpenAI: {e}")
        return f"Error de OpenAI: {e}"
    except Exception as e:
        print(f"Error general en interactuar_con_openai: {e}")
        return "Error: Problema inesperado al procesar tu solicitud."



@app.get("/")
def home():
    return {"mensaje": "Bienvenido al asistente del Lic. Daniel O. Bustamante"}
