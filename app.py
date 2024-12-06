import time
import threading
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import openai
import os

# Configuración de la clave de API
openai.api_key = os.getenv("OPENAI_API_KEY")

# Inicialización de la aplicación FastAPI
app = FastAPI()

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cambiar "*" por una lista de dominios permitidos si es necesario
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def init_db():
    """Inicializa la base de datos SQLite y crea la tabla si no existe."""
    db_path = os.path.abspath("palabras_clave.db")  # Ruta absoluta para evitar confusiones
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS palabras_clave (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                palabra TEXT UNIQUE NOT NULL,
                categoria TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()
        print(f"Base de datos creada o abierta con éxito en: {db_path}")
    except sqlite3.Error as e:
        print(f"Error al inicializar la base de datos: {e}")


# Lógica para registrar palabras clave nuevas
def registrar_palabra_clave(palabra: str, categoria: str):
    try:
        conn = sqlite3.connect("palabras_clave.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO palabras_clave (palabra, categoria) VALUES (?, ?)", (palabra, categoria))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error al registrar palabra clave: {e}")

def obtener_palabras_clave():
    conn = sqlite3.connect("palabras_clave.db")
    cursor = conn.cursor()
    cursor.execute("SELECT palabra FROM palabras_clave")
    palabras = [row[0] for row in cursor.fetchall()]
    conn.close()
    return palabras

# Simulación de sesiones (almacenamiento en memoria)
user_sessions = {}
SESSION_TIMEOUT = 60  # Tiempo de inactividad permitido en segundos

class UserInput(BaseModel):
    mensaje: str
    user_id: str

# Ruta inicial
@app.get("/")
def read_root():
    return {"message": "Bienvenido al asistente"}

# Evento de inicio
def verificar_permisos():
    ruta_actual = os.getcwd()
    archivo_prueba = os.path.join(ruta_actual, "prueba_escritura.txt")
    try:
        # Intenta escribir un archivo de prueba
        with open(archivo_prueba, "w") as archivo:
            archivo.write("Prueba de escritura exitosa.")
        print(f"Permisos de escritura confirmados en: {ruta_actual}")
        # Borra el archivo de prueba
        os.remove(archivo_prueba)
    except Exception as e:
        print(f"No tienes permisos de escritura en: {ruta_actual}. Error: {e}")

verificar_permisos()

@app.on_event("startup")
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

# Endpoint principal
@app.post("/asistente")
async def asistente(input_data: UserInput):
    try:
        user_id = input_data.user_id
        mensaje_usuario = input_data.mensaje.strip().lower()

        if not mensaje_usuario:
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

        # Inicializar sesión si no existe
        if user_id not in user_sessions:
            user_sessions[user_id] = {
                "contador_interacciones": 0,
                "ultima_interaccion": time.time(),
                "ultimo_mensaje": None,
            }
        else:
            user_sessions[user_id]["ultima_interaccion"] = time.time()
            
        user_sessions[user_id]["contador_interacciones"] += 1
        interacciones = user_sessions[user_id]["contador_interacciones"]

        # Manejo explícito del mensaje "si" y similares
        if mensaje_usuario in ["si", "sí", "si claro", "sí claro"]:
            if user_sessions[user_id]["ultimo_mensaje"] in ["si", "sí", "si claro", "sí claro"]:
                return {"respuesta": "Ya confirmaste eso. ¿Hay algo más en lo que pueda ayudarte?"}
            user_sessions[user_id]["ultimo_mensaje"] = mensaje_usuario
            return {"respuesta": "Comprendo. ¿Qué puedo hacer por vos al respecto?"}

        # Detectar palabras clave
        palabras_existentes = obtener_palabras_clave()
        nuevas_palabras = [
            palabra for palabra in mensaje_usuario.split() if palabra not in palabras_existentes
        ]

        # Registrar palabras clave nuevas
        for palabra in nuevas_palabras:
            registrar_palabra_clave(palabra, "categoría pendiente")

        # Reiniciar conversación
        if mensaje_usuario == "reiniciar":
            user_sessions.pop(user_id, None)
            return {"respuesta": "La conversación ha sido reiniciada. Puedes empezar de nuevo."}

        # Limitar el número de interacciones
        if interacciones >= 6:
            return {
                "respuesta": (
                    "Si bien tengo que dar por terminada esta conversación, no obstante si lo considerás necesario, "
                    "podés contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 "
                    "para una evaluación más profunda de tu condición emocional. Si querés reiniciar un nuevo chat escribí: reiniciar."
                )
            }
        
        if interacciones == 5:
            return {
                "respuesta": (
                    "Comprendo perfectamente. Si lo considerás necesario, "
                    "contactá al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 "
                    "para una evaluación más profunda de tu situación personal."
                )
            }

        # Interactuar con OpenAI
        respuesta = await interactuar_con_openai(mensaje_usuario)
        return {"respuesta": respuesta}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# Interacción con OpenAI
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
