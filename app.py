import os
import time
import sqlite3
import asyncio
import shutil
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from difflib import SequenceMatcher  # Importación para calcular similitud

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
    allow_origins=["*"],  # Cambiar "*" a una lista de dominios específicos si es necesario
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ruta para la base de datos
DB_PATH = "./data/palabras_clave.db"  # Cambiar según sea necesario

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

# Inicialización de la base de datos
def init_db():
    """
    Inicializa la base de datos creando la tabla 'palabras_clave' si no existe.
    """
    try:
        # Asegurar que el directorio de la base de datos exista
        db_directory = os.path.dirname(DB_PATH)
        if not os.path.exists(db_directory):
            os.makedirs(db_directory)

        # Conexión a la base de datos
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Crear tabla si no existe
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
        print("Base de datos inicializada correctamente.")
    except sqlite3.Error as db_error:
        print(f"Error al inicializar la base de datos: {db_error}")
    except Exception as e:
        print(f"Error inesperado al inicializar la base de datos: {e}")

# Limpieza de sesiones inactivas
async def session_cleaner():
    """
    Limpia sesiones inactivas basadas en `SESSION_TIMEOUT`.
    """
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
            await asyncio.sleep(60)  # Pausa antes de la próxima limpieza
        except Exception as e:
            print(f"Error en el limpiador de sesiones: {e}")

@app.on_event("startup")
async def startup_event():
    """
    Eventos de inicio de la aplicación.
    """
    print("Iniciando la aplicación...")
    init_db()  # Inicializar la base de datos
    asyncio.create_task(session_cleaner())  # Iniciar limpiador de sesiones

# Analizar mensaje del usuario con cuadros psicológicos
def analizar_mensaje_usuario_con_cuadros(mensaje_usuario: str) -> dict:
    """
    Analiza un mensaje del usuario y busca palabras clave en la base de datos.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        palabras_clave = mensaje_usuario.split()
        if not palabras_clave:
            return {"error": "El mensaje proporcionado está vacío o no contiene información válida."}

        consulta = f"""
            SELECT palabra, categoria 
            FROM palabras_clave 
            WHERE palabra IN ({','.join(['?'] * len(palabras_clave))})
        """
        cursor.execute(consulta, palabras_clave)
        resultados = cursor.fetchall()
        conn.close()

        if not resultados:
            return {"mensaje": "No se encontraron coincidencias en la base de datos para los síntomas proporcionados."}

        categorias = {}
        for palabra, categoria in resultados:
            if categoria not in categorias:
                categorias[categoria] = []
            categorias[categoria].append(palabra)

        return {"categorias": categorias}

    except sqlite3.Error as db_error:
        print(f"Error en la base de datos: {db_error}")
        return {"error": "Hubo un problema técnico al acceder a la base de datos."}
    except Exception as e:
        print(f"Error inesperado: {e}")
        return {"error": "Ocurrió un error inesperado mientras procesaba tu información."}

# Endpoint principal para interacción con el asistente
@app.post("/asistente")
async def asistente(input_data: UserInput):
    """
    Endpoint para manejar la interacción con el asistente.
    """
    try:
        user_id = input_data.user_id
        mensaje_usuario = normalizar_texto(input_data.mensaje)

        if not mensaje_usuario:
            raise HTTPException(
                status_code=400,
                detail="Tu mensaje parece estar vacío. Por favor, cuéntame más sobre cómo te sientes o qué necesitas."
            )

        # Inicializar sesión del usuario si no existe
        if user_id not in user_sessions:
            user_sessions[user_id] = {
                "contador_interacciones": 0,
                "ultima_interaccion": time.time(),
                "mensajes": [],  # Cambiado a lista para comparar similitud
            }
            bienvenida = (
                "¡Hola! Soy tu asistente virtual. Estoy aquí para escucharte y ayudarte. "
                "Puedes compartir cualquier síntoma, preocupación o situación que estés experimentando. "
                "Tómate tu tiempo para escribir, estoy aquí para ti."
            )
            return {"respuesta": bienvenida}

        # Actualizar la sesión del usuario
        user_sessions[user_id]["ultima_interaccion"] = time.time()
        user_sessions[user_id]["contador_interacciones"] += 1

        # Verificar si el mensaje es similar a otros ya mencionados
        for mensaje_previo in user_sessions[user_id]["mensajes"]:
            if son_similares(mensaje_usuario, mensaje_previo):
                return {
                    "respuesta": "Ya hemos hablado de eso. ¿Qué más te está afectando en este momento?"
                }

        # Registrar el mensaje
        user_sessions[user_id]["mensajes"].append(mensaje_usuario)
        interacciones = user_sessions[user_id]["contador_interacciones"]

        # Proveer retroalimentación al usuario
        if interacciones < 5:
            respuestas = [
                "Entiendo. ¿Puedes contarme más sobre lo que estás sintiendo o algo más que te preocupe?",
                "Gracias por abrirte conmigo. ¿Hay algún otro aspecto que te gustaría compartir?",
                "Estoy aquí para escucharte. ¿Qué más te gustaría contarme sobre lo que sientes?",
                "Cuéntame más, estoy aquí para apoyarte. ¿Hay algo más que te esté afectando?"
            ]
            return {"respuesta": respuestas[interacciones % len(respuestas)]}

        # Análisis de síntomas después de 5 interacciones
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

            categorias_detectadas = resultado_analisis.get("categorias", {})

            respuestas_por_categoria = {
                "ansiedad": "Parece que estás lidiando con síntomas de ansiedad. ¿Hay algo que creas que pueda estar desencadenándola?",
                "depresion": "Entiendo que podrías estar experimentando síntomas relacionados con la depresión. Es importante hablar con alguien sobre ello.",
                "estres": "El estrés puede ser muy abrumador. ¿Puedes identificar qué podría estar causándolo?",
            }

            respuestas = []
            for categoria, palabras in categorias_detectadas.items():
                respuesta = respuestas_por_categoria.get(categoria.lower(), None)
                if respuesta:
                    respuestas.append(f"{respuesta} Palabras relacionadas: {', '.join(palabras)}.")

            if respuestas:
                respuesta_final = " ".join(respuestas)
            else:
                respuesta_final = "He detectado algunas categorías, pero parece que necesito más información para ayudarte mejor."

            return {
                "respuesta": (
                    f"Gracias por compartir más detalles. Esto es lo que he podido analizar: \n{respuesta_final}\n\n"
                    "Te sugiero contactar al Lic. Daniel O. Bustamante, un profesional especializado, "
                    "al WhatsApp +54 911 3310-1186. Él podrá ofrecerte una evaluación y un apoyo más completo."
                )
            }

        # Mensaje de cierre después de 6 interacciones
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

# Endpoint para formulario de subida
@app.get("/upload_form", response_class=HTMLResponse)
async def upload_form():
    """
    Muestra un formulario HTML para subir la base de datos.
    """
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

# Endpoint para descargar el archivo de base de datos
@app.get("/download/palabras_clave.db")
async def download_file():
    """
    Descarga el archivo de la base de datos.
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
    return FileResponse(DB_PATH, media_type="application/octet-stream", filename="palabras_clave.db")

# Endpoint para subir el archivo de base de datos
@app.post("/upload_file")
async def upload_file(file: UploadFile = File(...)):
    """
    Sube un nuevo archivo de base de datos.
    """
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
