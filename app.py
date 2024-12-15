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
DB_PATH = "/var/data/palabras_clave.db"  # Cambia esta ruta según el disco persistente

# Configuración de la base de datos SQLite
def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS palabras_clave (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                palabra TEXT UNIQUE NOT NULL,
                categoria TEXT NOT NULL,
                cuadros TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")

# Registrar palabra clave nueva
def registrar_palabra_clave(palabra: str, categoria: str, cuadros: str):
    """
    Registra palabras clave relacionadas exclusivamente con estados emocionales
    o problemas psicológicos.
    """
    categorias_validas = ["depresión", "ansiedad", "ira", "estrés", "tristeza", "miedo", "inseguridad"]
    if categoria.lower() not in categorias_validas:
        return  # Solo registrar si la categoría es válida

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO palabras_clave (palabra, categoria, cuadros) VALUES (?, ?, ?)", (palabra, categoria, cuadros))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error al registrar palabra clave: {e}")

# Obtener palabras clave existentes
def obtener_palabras_clave():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT palabra FROM palabras_clave")
        palabras = [row[0] for row in cursor.fetchall()]
        conn.close()
        return palabras
    except Exception as e:
        print(f"Error al obtener palabras clave: {e}")
        return []

# Clase para solicitudes del usuario
class UserInput(BaseModel):
    mensaje: str
    user_id: str

# Gestión de sesiones (en memoria)
user_sessions = {}

@app.on_event("startup")
def startup_event():
    init_db()

# Analizar mensaje del usuario con cuadros psicológicos
def analizar_mensaje_usuario_con_cuadros(mensaje_usuario: str) -> str:
    """
    Analiza el mensaje del usuario buscando palabras clave en la base de datos,
    identifica categorías asociadas y genera un análisis con cuadros psicológicos.
    """
    try:
        # Conectar a la base de datos
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Dividir el mensaje en palabras para buscar coincidencias
        palabras_clave = mensaje_usuario.split()
        if not palabras_clave:
            return "El mensaje proporcionado está vacío o no contiene información válida."

        # Construir y ejecutar la consulta SQL
        consulta = f"""
            SELECT palabra, categoria, cuadros 
            FROM palabras_clave 
            WHERE palabra IN ({','.join(['?'] * len(palabras_clave))})
        """
        cursor.execute(consulta, palabras_clave)
        resultados = cursor.fetchall()

        # Cerrar la conexión
        conn.close()

        # Si no se encuentran coincidencias
        if not resultados:
            return "No se encontraron coincidencias en la base de datos para los síntomas proporcionados."

        # Procesar los resultados
        categorias = {}
        cuadros_detectados = set()
        for palabra, categoria, cuadro in resultados:
            if categoria not in categorias:
                categorias[categoria] = []
            categorias[categoria].append(palabra)
            if cuadro:  # Evitar cuadros nulos o vacíos
                cuadros_detectados.add(cuadro)

        # Generar el análisis detallado
        detalles_categorias = []
        for categoria, palabras in categorias.items():
            detalles_categorias.append(f"{categoria}: {' '.join(palabras)}")

        detalles_cuadros = ", ".join(cuadros_detectados) if cuadros_detectados else "No se detectaron cuadros específicos."

        return (
            f"Categorías detectadas:\n{'\n'.join(detalles_categorias)}\n\n"
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
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

        # Inicializar sesión si no existe
        if user_id not in user_sessions:
            user_sessions[user_id] = {
                "contador_interacciones": 0,
                "mensajes": [],
            }

        user_sessions[user_id]["contador_interacciones"] += 1
        interacciones = user_sessions[user_id]["contador_interacciones"]

        # Registrar mensaje del usuario
        user_sessions[user_id]["mensajes"].append(mensaje_usuario)

        # Interacción 5: Sugerir contactar y describir estados emocionales
        if interacciones == 5:
            sintomas_usuario = " ".join(user_sessions[user_id]["mensajes"])
            resultado_analisis = analizar_mensaje_usuario_con_cuadros(sintomas_usuario)
            return {
                "respuesta": (
                    f"{resultado_analisis}\n\n"
                    "Con base en este análisis, te sugiero contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186. "
                    "Él podrá realizar una evaluación más profunda y ayudarte en tu proceso de recuperación."
                )
            }

        # Interacción 6: Concluir la conversación
        if interacciones == 6:
            sintomas_usuario = " ".join(user_sessions[user_id]["mensajes"])
            resultado_analisis = analizar_mensaje_usuario_con_cuadros(sintomas_usuario)
            user_sessions.pop(user_id, None)  # Limpiar la sesión
            return {
                "respuesta": (
                    f"Hemos analizado tus mensajes: {resultado_analisis}\n\n"
                    "Para garantizar que recibas el apoyo adecuado, te recomiendo contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186. "
                    "Él podrá brindarte una evaluación detallada y un acompañamiento profesional en este proceso. "
                    "Gracias por confiar en este servicio. La conversación ha concluido."
                )
            }

        # Responder durante las primeras interacciones (1 a 4)
        if interacciones < 5:
            respuesta_ai = await interactuar_con_openai(mensaje_usuario)
            return {"respuesta": respuesta_ai}

    except Exception as e:
        print(f"Error interno: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# Interacción con OpenAI
async def interactuar_con_openai(mensaje_usuario: str) -> str:
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres un asistente profesional que analiza síntomas emocionales."},
                {"role": "user", "content": mensaje_usuario}
            ],
            max_tokens=200,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al comunicarse con OpenAI: {str(e)}")

# Endpoint para descargar el archivo de base de datos
@app.get("/download/palabras_clave.db")
async def download_file():
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="El archivo palabras_clave.db no se encuentra.")
    return FileResponse(DB_PATH, media_type="application/octet-stream", filename="palabras_clave.db")

# Endpoint para subir el archivo de base de datos
@app.post("/upload_file")
async def upload_file(file: UploadFile = File(...)):
    try:
        if file.filename != "palabras_clave.db":
            raise HTTPException(status_code=400, detail="El archivo debe llamarse 'palabras_clave.db'.")

        file_path = DB_PATH
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Verificar si el archivo es una base de datos SQLite válida
        try:
            conn = sqlite3.connect(file_path)
            conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
            conn.close()
        except Exception:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail="El archivo subido no es una base de datos SQLite válida.")

        return {"message": "Archivo subido exitosamente.", "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir el archivo: {str(e)}")

# Formulario HTML para subir el archivo de base de datos
@app.get("/upload_form", response_class=HTMLResponse)
async def upload_form():
    """
    Genera un formulario simple para subir el archivo palabras_clave.db.
    """
    return """
    <!doctype html>
    <html>
    <head>
        <title>Subir palabras_clave.db</title>
    </head>
    <body>
        <h1>Subir un nuevo archivo palabras_clave.db</h1>
        <form action="/upload_file" method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept=".db">
            <button type="submit">Subir</button>
        </form>
    </body>
    </html>
    """

