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
PRUEBA_PATH = "/var/data/prueba_escritura.txt"

# Configuración de la base de datos SQLite
def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS palabras_clave (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                palabra TEXT UNIQUE NOT NULL,
                categoria TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interacciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                consulta TEXT NOT NULL,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
        print(f"Base de datos creada o abierta en: {DB_PATH}")
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")

# Registrar palabra clave nueva
def registrar_palabra_clave(palabra: str, categoria: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO palabras_clave (palabra, categoria) VALUES (?, ?)", (palabra, categoria))
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

# Obtener categorías asociadas a los síntomas
def obtener_categorias(sintomas):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        categorias = set()
        for sintoma in sintomas:
            cursor.execute("SELECT categoria FROM palabras_clave WHERE palabra LIKE ?", (f"%{sintoma}%",))
            resultados = cursor.fetchall()
            for resultado in resultados:
                categorias.add(resultado[0])
        conn.close()
        return list(categorias)
    except Exception as e:
        print(f"Error al obtener categorías: {e}")
        return []

# Verificar escritura en disco
def verificar_escritura_en_disco():
    try:
        with open(PRUEBA_PATH, "w") as archivo:
            archivo.write("Prueba de escritura exitosa.")
    except Exception as e:
        print(f"Error al escribir en el disco: {e}")

# Clase para solicitudes del usuario
class UserInput(BaseModel):
    mensaje: str
    user_id: str

# Gestión de sesiones (en memoria)
user_sessions = {}
SESSION_TIMEOUT = 30  # Tiempo de inactividad en segundos

@app.on_event("startup")
def startup_event():
    verificar_escritura_en_disco()  # Prueba de escritura
    init_db()  # Inicializar base de datos
    start_session_cleaner()  # Iniciar limpieza de sesiones

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

# Endpoint inicial
@app.get("/")
def read_root():
    return {"message": "Bienvenido al asistente"}

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
        with open(DB_PATH, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return {"message": "Archivo subido exitosamente.", "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir el archivo: {str(e)}")

# Formulario para subir archivo
@app.get("/upload_form", response_class=HTMLResponse)
async def upload_form():
    return """
    <!doctype html>
    <html>
    <head>
        <title>Subir palabras_clave.db</title>
    </head>
    <body>
        <h1>Subir un nuevo archivo palabras_clave.db</h1>
        <form action="/upload_file" method="post" enctype="multipart/form-data">
            <input type="file" name="file">
            <button type="submit">Subir</button>
        </form>
    </body>
    </html>
    """

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
                "ultima_interaccion": time.time(),
                "ultimo_mensaje": None,
                "sintomas": []
            }
        else:
            user_sessions[user_id]["ultima_interaccion"] = time.time()

        user_sessions[user_id]["contador_interacciones"] += 1
        interacciones = user_sessions[user_id]["contador_interacciones"]

        # Detener respuestas después de la interacción 6
        if interacciones > 6:
            return

        # Guardar síntomas mencionados por el usuario
        sintomas_usuario = mensaje_usuario.split()
        user_sessions[user_id]["sintomas"].extend(sintomas_usuario)

        # Reinicio de conversación
        if mensaje_usuario == "reiniciar":
            if user_id in user_sessions:
                user_sessions.pop(user_id)
                return {"respuesta": "La conversación ha sido reiniciada. Empezá de nuevo cuando quieras."}
            else:
                return {"respuesta": "No se encontró una sesión activa. Empezá una nueva conversación cuando quieras."}

        # Manejo de "sí"
        if mensaje_usuario in ["si", "sí", "si claro", "sí claro"]:
            if user_sessions[user_id]["ultimo_mensaje"] in ["si", "sí", "si claro", "sí claro"]:
                return {"respuesta": "Ya confirmaste eso. ¿Hay algo más en lo que pueda ayudarte?"}
            user_sessions[user_id]["ultimo_mensaje"] = mensaje_usuario
            return {"respuesta": "Entendido. ¿Qué más puedo hacer por vos?"}

        # Detectar y registrar nuevas palabras clave
        palabras_existentes = obtener_palabras_clave()
        nuevas_palabras = [
            palabra for palabra in mensaje_usuario.split() if palabra not in palabras_existentes
        ]
        for palabra in nuevas_palabras:
            registrar_palabra_clave(palabra, "categoría pendiente")

        # Mensaje de finalización de conversación
        if interacciones == 6:
            categorias_detectadas = obtener_categorias(user_sessions[user_id]["sintomas"])
            sintomas_unicos = set(user_sessions[user_id]["sintomas"])
            categorias_texto = ", ".join(categorias_detectadas)

            return {
                "respuesta": (
                    f"Si bien tengo que cerrar esta conversación, igualmente insisto que tus síntomas de {', '.join(sintomas_unicos)} "
                    f"podrían estar asociados estados o cuadros de {categorias_texto}. "
                    "Te sugiero contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 para una evaluación más profunda. "
                    "Si querés reiniciar un nuevo chat escribí: **reiniciar**."
                )
            }

        if interacciones == 5:
            categorias_detectadas = obtener_categorias(user_sessions[user_id]["sintomas"])
            sintomas_unicos = set(user_sessions[user_id]["sintomas"])
            categorias_texto = ", ".join(categorias_detectadas)

            return {
                "respuesta": (
                    f"Comprendo perfectamente, tus síntomas de {', '.join(sintomas_unicos)} "
                    f"podrían estar relacionados afecciónes tales como {categorias_texto}. "
                    "Si lo considerás necesario, te sugiero contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 "
                    "para una evaluación más profunda de tu situación personal."
                )
            }

        # Interacción con OpenAI
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
