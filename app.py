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

# Configuración de la clave de API de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("OPENAI_API_KEY no está configurada en las variables de entorno.")

# Inicialización de FastAPI
app = FastAPI()

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cambiar "*" a una lista de dominios específicos si es necesario
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ruta para la base de datos
DB_PATH = "/var/data/palabras_clave.db"  # Cambiar según sea necesario

# Clase para solicitudes del usuario
class UserInput(BaseModel):
    mensaje: str
    user_id: str

# Gestión de sesiones (en memoria)
user_sessions = {}
SESSION_TIMEOUT = 60  # Tiempo de inactividad en segundos

@app.on_event("startup")
def startup_event():
    init_db()
    start_session_cleaner()

# Inicialización de la base de datos

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS palabras_clave (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                palabra TEXT UNIQUE NOT NULL,
                categoria TEXT NOT NULL,
                cuadros TEXT
            )
            """
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")

# Limpieza de sesiones inactivas

def start_session_cleaner():
    def cleaner():
        while True:
            current_time = time.time()
            inactive_users = [
                user_id
                for user_id, data in user_sessions.items()
                if current_time - data["ultima_interaccion"] > SESSION_TIMEOUT
            ]
            for user_id in inactive_users:
                user_sessions.pop(user_id, None)
            time.sleep(60)

    thread = threading.Thread(target=cleaner, daemon=True)
    thread.start()

# Analizar mensaje del usuario con cuadros psicológicos

def analizar_mensaje_usuario_con_cuadros(mensaje_usuario: str) -> str:
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        palabras_clave = mensaje_usuario.split()
        if not palabras_clave:
            return "El mensaje proporcionado está vacío o no contiene información válida."

        consulta = f"""
            SELECT palabra, categoria, cuadros 
            FROM palabras_clave 
            WHERE palabra IN ({','.join(['?'] * len(palabras_clave))})
        """
        cursor.execute(consulta, palabras_clave)
        resultados = cursor.fetchall()
        conn.close()

        if not resultados:
            return "No se encontraron coincidencias en la base de datos para los síntomas proporcionados."

        categorias = {}
        cuadros_detectados = set()
        for palabra, categoria, cuadro in resultados:
            if categoria not in categorias:
                categorias[categoria] = []
            categorias[categoria].append(palabra)
            if cuadro:
                cuadros_detectados.add(cuadro)

        detalles_categorias = [
            f"{categoria}: {' '.join(palabras)}" for categoria, palabras in categorias.items()
        ]

        detalles_cuadros = (
            ", ".join(cuadros_detectados)
            if cuadros_detectados
            else "No se detectaron cuadros específicos."
        )

        return (
            f"Categorías detectadas:\n{chr(10).join(detalles_categorias)}\n\n"
            f"Probabilidad de los siguientes cuadros psicológicos: {detalles_cuadros}."
        )

    except sqlite3.Error as db_error:
        print(f"Error en la base de datos: {db_error}")
        return "Hubo un error al acceder a la base de datos. Por favor, intenta nuevamente más tarde."
    except Exception as e:
        print(f"Error inesperado: {e}")
        return "Hubo un error al analizar los síntomas. Por favor, intenta nuevamente más tarde."

# Endpoint principal para interacción con el asistente
@app.post("/asistente")
async def asistente(input_data: UserInput):
    try:
        user_id = input_data.user_id
        mensaje_usuario = input_data.mensaje.strip().lower()

        if not mensaje_usuario:
            raise HTTPException(
                status_code=400, detail="El mensaje no puede estar vacío."
            )

        if user_id not in user_sessions:
            user_sessions[user_id] = {
                "contador_interacciones": 0,
                "ultima_interaccion": time.time(),
                "mensajes": [],
            }
        else:
            user_sessions[user_id]["ultima_interaccion"] = time.time()

        user_sessions[user_id]["contador_interacciones"] += 1
        interacciones = user_sessions[user_id]["contador_interacciones"]

        user_sessions[user_id]["mensajes"].append(mensaje_usuario)

        if interacciones == 5:
            sintomas_usuario = " ".join(user_sessions[user_id]["mensajes"])
            resultado_analisis = analizar_mensaje_usuario_con_cuadros(sintomas_usuario)
            return {
                "respuesta": (
                    f"En base a los síntomas proporcionados, se recomienda contactar al Lic. Daniel O. Bustamante 
                    "al WhatsApp +54 911 3310-1186 para una evaluación profesional. {resultado_analisis}"
                )
            }

        if interacciones == 6:
            user_sessions.pop(user_id, None)
            return {
                "respuesta": (
                    "Gracias por utilizar el servicio. Se recomienda seguimiento profesional."
                )
            }

        return {
            "respuesta": f"Mensaje recibido: '{mensaje_usuario}'. Por favor, continúe."
        }

    except Exception as e:
        print(f"Error interno: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# Endpoint para descargar el archivo de base de datos
@app.get("/download/palabras_clave.db")
async def download_file():
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
    return FileResponse(DB_PATH, media_type="application/octet-stream", filename="palabras_clave.db")

# Endpoint para subir el archivo de base de datos
@app.post("/upload_file")
async def upload_file(file: UploadFile = File(...)):
    try:
        if file.filename != "palabras_clave.db":
            raise HTTPException(
                status_code=400, detail="El archivo debe llamarse 'palabras_clave.db'."
            )

        file_path = DB_PATH
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        conn = sqlite3.connect(file_path)
        conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
        conn.close()

        return {"message": "Archivo subido exitosamente.", "filename": file.filename}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error al subir el archivo: {str(e)}"
        )
