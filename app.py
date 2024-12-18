import os
import time
import sqlite3
import asyncio
import shutil
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from difflib import SequenceMatcher
import nltk
from nltk.corpus import wordnet

# Descargar recursos de nltk
nltk.download('wordnet')

# Configuración de la clave de API de OpenAI
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("OPENAI_API_KEY no está configurada en las variables de entorno.")

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

# Ruta para la base de datos
DB_PATH = "./data/palabras_clave.db"

# Gestión de sesiones (en memoria)
user_sessions = {}
SESSION_TIMEOUT = 60  # Tiempo de inactividad en segundos

# Clase para solicitudes del usuario
class UserInput(BaseModel):
    mensaje: str
    user_id: str

# Función para normalizar texto
def normalizar_texto(texto):
    return ''.join(c for c in texto.lower() if c.isalnum() or c.isspace()).strip()

# Función para calcular similitud entre textos
def son_similares(texto1, texto2, umbral=0.8):
    similitud = SequenceMatcher(None, texto1, texto2).ratio()
    return similitud >= umbral

# Función para obtener sinónimos de una palabra
def obtener_sinonimos(palabra):
    sinonimos = set()
    for syn in wordnet.synsets(palabra):
        for lemma in syn.lemmas():
            sinonimos.add(lemma.name().replace('_', ' ').lower())
    return sinonimos

# Inicialización de la base de datos
def init_db():
    try:
        db_directory = os.path.dirname(DB_PATH)
        if not os.path.exists(db_directory):
            os.makedirs(db_directory)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS palabras_clave (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sintoma TEXT UNIQUE NOT NULL,
                cuadro TEXT NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()
        print("Base de datos inicializada correctamente.")
    except sqlite3.Error as db_error:
        print(f"Error al inicializar la base de datos: {db_error}")
    except Exception as e:
        print(f"Error inesperado al inicializar la base de datos: {e}")

# Limpieza de sesiones inactivas
async def session_cleaner():
    while True:
        try:
            current_time = time.time()
            inactive_users = [
                user_id
                for user_id, data in user_sessions.items()
                if current_time - data.get("ultima_interaccion", 0) > SESSION_TIMEOUT
            ]
            for user_id in inactive_users:
                user_sessions.pop(user_id, None)
            await asyncio.sleep(60)
        except Exception as e:
            print(f"Error en el limpiador de sesiones: {e}")

@app.on_event("startup")
async def startup_event():
    print("Iniciando la aplicación...")
    init_db()
    asyncio.create_task(session_cleaner())

# Analizar mensaje del usuario con cuadros psicológicos
def analizar_mensaje_usuario_con_cuadros(mensaje_usuario: str) -> dict:
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        palabras_clave = mensaje_usuario.split()
        if not palabras_clave:
            return {"mensaje": "El mensaje proporcionado está vacío o no contiene información válida."}

        consulta = "SELECT sintoma, cuadro FROM palabras_clave WHERE LOWER(sintoma) LIKE ?"
        cuadros = {}

        for palabra in palabras_clave:
            sinonimos = obtener_sinonimos(palabra)
            sinonimos.add(palabra)

            for sinonimo in sinonimos:
                cursor.execute(consulta, (f"%{sinonimo.lower()}%",))
                resultados = cursor.fetchall()

                for sintoma, cuadro in resultados:
                    if cuadro not in cuadros:
                        cuadros[cuadro] = []
                    cuadros[cuadro].append(sintoma)

        conn.close()

        if not cuadros:
            return {"mensaje": "No se encontraron coincidencias en la base de datos para los síntomas proporcionados."}

        return {"cuadros": cuadros}

    except sqlite3.Error as db_error:
        print(f"Error en la base de datos: {db_error}")
        return {"error": "Hubo un problema técnico al acceder a la base de datos."}
    except Exception as e:
        print(f"Error inesperado: {e}")
        return {"error": "Ocurrió un error inesperado mientras procesaba tu información."}

# Endpoint principal para interacción con el asistente
@app.post("/asistente")
async def asistente(input_data: UserInput):
    try:
        user_id = input_data.user_id
        mensaje_usuario = normalizar_texto(input_data.mensaje)

        if not mensaje_usuario:
            raise HTTPException(
                status_code=400,
                detail="Tu mensaje parece estar vacío. Por favor, cuéntame más sobre cómo te sientes o qué necesitas."
            )

        if user_id not in user_sessions:
            user_sessions[user_id] = {
                "contador_interacciones": 0,
                "ultima_interaccion": time.time(),
                "mensajes": [],
            }
            bienvenida = (
                "¡Hola! Soy tu asistente virtual. Estoy aquí para escucharte y ayudarte. "
                "Puedes compartir cualquier síntoma, preocupación o situación que estés experimentando. "
                "Tómate tu tiempo para escribir, estoy aquí para ti."
            )
            return {"respuesta": bienvenida}

        user_sessions[user_id]["ultima_interaccion"] = time.time()
        user_sessions[user_id]["contador_interacciones"] += 1

        # Lista de mensajes genéricos que no activarán la respuesta de repetición
        mensajes_excluidos = ["hola", "buenos días", "buenas tardes", "buenas noches"]

        # Verificar si el mensaje es genérico o similar a mensajes previos
        if mensaje_usuario not in mensajes_excluidos:
            for mensaje_previo in user_sessions[user_id]["mensajes"]:
                if son_similares(mensaje_usuario, mensaje_previo):
                    return {
                        "respuesta": "Ya hemos hablado de eso. ¿Qué más te está afectando en este momento?"
                    }

        user_sessions[user_id]["mensajes"].append(mensaje_usuario)
        interacciones = user_sessions[user_id]["contador_interacciones"]

        if interacciones < 5:
            respuestas = [
                "Entiendo. ¿Puedes contarme más sobre lo que estás sintiendo o algo más que te preocupe?",
                "Gracias por abrirte conmigo. ¿Hay algún otro aspecto que te gustaría compartir?",
                "Estoy aquí para escucharte. ¿Qué más te gustaría contarme sobre lo que sientes?",
                "Cuéntame más, estoy aquí para apoyarte. ¿Hay algo más que te esté afectando?"
            ]
            return {"respuesta": respuestas[interacciones % len(respuestas)]}

        if interacciones == 5:
            sintomas_usuario = " ".join(user_sessions[user_id]["mensajes"])
            resultado_analisis = analizar_mensaje_usuario_con_cuadros(sintomas_usuario)

            if "error" in resultado_analisis:
                return {
                    "respuesta": (
                        "Lamento mucho este inconveniente. Parece que hubo un problema técnico mientras procesaba tu información. "
                        "Por favor, intenta nuevamente más tarde o, si es urgente, contacta directamente al Lic. Daniel O. Bustamante "
                        "al WhatsApp +54 911 3310-1186 para recibir ayuda profesional inmediata."
                    )
                }

            cuadros_detectados = resultado_analisis.get("cuadros", {})

            if cuadros_detectados:
                lista_respuestas = []
                for cuadro, sintomas in cuadros_detectados.items():
                    lista_respuestas.append(f"{cuadro}: {', '.join(sintomas)}")

                respuesta_final = (
                    f"En base a los síntomas referidos, se han identificado las siguientes categorías: {'. '.join(lista_respuestas)}. "
                    "Te sugiero contactar al Lic. Daniel O. Bustamante, un profesional especializado, al WhatsApp +54 911 3310-1186. "
                    "Él podrá ofrecerte una evaluación y un apoyo más completo."
                )

                return {"respuesta": respuesta_final}

            else:
                return {
                    "respuesta": "No se detectaron suficientes coincidencias para determinar un cuadro específico. Si persisten los síntomas, te sugiero buscar apoyo profesional."
                }

        if interacciones == 6:
            return {
                "respuesta": (
                    "Muchas gracias por confiar en mí y compartir tus pensamientos. "
                    "Si necesitas más ayuda, no dudes en buscar apoyo profesional. ¡Te deseo lo mejor!"
                )
            }

    except Exception as e:
        print(f"Error interno: {e}")
        raise HTTPException(
            status_code=500,
            detail="Lo siento, hubo un problema interno al procesar tu solicitud. Por favor, inténtalo de nuevo más tarde."
        )

@app.get("/upload_form", response_class=HTMLResponse)
async def upload_form():
    return """
    <html>
        <body>
            <h1>Subir archivo de base de datos</h1>
            <form action="/upload_file" method="post" enctype="multipart/form-data">
                <input type="file" name="file" />
                <button type="submit">Subir</button>
            </form>
        </body>
    </html>
    """

@app.get("/download/palabras_clave.db")
async def download_file():
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
    return FileResponse(DB_PATH, media_type="application/octet-stream", filename="palabras_clave.db")

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
