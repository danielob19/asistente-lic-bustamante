import time
import threading
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai
import json
import os

# Archivos para base de conocimiento y síntomas mencionados
base_de_conocimiento_path = "base_de_conocimiento.json"
sintomas_guardados_path = "sintomas_mencionados.json"

# Cargar o crear la base de conocimiento
if os.path.exists(base_de_conocimiento_path):
    with open(base_de_conocimiento_path, "r") as file:
        base_de_conocimiento = json.load(file)
else:
    base_de_conocimiento = {
        "angustia": "cuadro de angustia",
        "nervioso": "nerviosismo",
        "ansiedad": "cuadro de ansiedad",
        "cansancio": "depresión",
        "atonito": "estrés",
        # Agrega más términos según sea necesario...
    }
    with open(base_de_conocimiento_path, "w") as file:
        json.dump(base_de_conocimiento, file, indent=4)

# Crear archivo de síntomas mencionados si no existe
if not os.path.exists(sintomas_guardados_path):
    with open(sintomas_guardados_path, "w") as file:
        json.dump([], file)

# Función para detectar palabras clave en el mensaje
def detectar_palabras_clave(mensaje):
    """Detecta palabras clave en el mensaje del usuario que coincidan con el diccionario."""
    palabras_detectadas = [
        palabra for palabra in mensaje.lower().split()
        if palabra in base_de_conocimiento
    ]
    return list(set(palabras_detectadas))  # Evitar duplicados

# Función para guardar palabras clave mencionadas en un archivo JSON
def guardar_sintomas_mencionados(sintomas):
    """Guarda los síntomas mencionados por el usuario en un archivo JSON."""
    if not sintomas:  # No hacer nada si no hay síntomas detectados
        return

    try:
        with open(sintomas_guardados_path, "r+") as file:
            datos_actuales = json.load(file)  # Leer datos existentes
            datos_actuales.extend(sintomas)  # Agregar nuevos síntomas
            datos_actuales = list(set(datos_actuales))  # Evitar duplicados
            file.seek(0)  # Volver al inicio del archivo para sobrescribir
            json.dump(datos_actuales, file, indent=4)  # Guardar en JSON
    except json.JSONDecodeError:
        # Si el archivo está vacío o corrupto, sobrescribirlo
        with open(sintomas_guardados_path, "w") as file:
            json.dump(sintomas, file, indent=4)
    except Exception as e:
        print(f"Error al guardar los síntomas: {e}")

# Ejemplo de uso
mensaje_usuario = "Me siento angustia y también algo nervioso."
palabras_detectadas = detectar_palabras_clave(mensaje_usuario)
guardar_sintomas_mencionados(palabras_detectadas)

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
            time.sleep(30)  # Ejecuta la limpieza cada 60 segundos

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
