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
from collections import Counter

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

# Clase para solicitudes del usuario
class UserInput(BaseModel):
    mensaje: str
    user_id: str

# Inicialización de la base de datos
def init_db():
    """
    Crea las tablas necesarias en la base de datos si no existen.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS palabras_clave (
                    Id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sintoma TEXT UNIQUE NOT NULL,
                    cuadro TEXT NOT NULL
                )
            """)
        print(f"Base de datos creada o abierta en: {DB_PATH}")
    except sqlite3.Error as e:
        print(f"Error al inicializar la base de datos: {e}")

# Registrar síntoma nuevo
def registrar_sintoma(sintoma: str, cuadro: str):
    """
    Registra un nuevo síntoma con su cuadro asociado en la base de datos.
    """
    if not sintoma or not cuadro:
        print("Error: El síntoma y el cuadro no pueden estar vacíos.")
        return
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO palabras_clave (sintoma, cuadro) VALUES (?, ?)",
                (sintoma.lower(), cuadro)
            )
            print(f"Sintoma '{sintoma}' registrado con el cuadro '{cuadro}'.")
    except sqlite3.Error as e:
        print(f"Error al registrar el síntoma: {e}")

# Obtener síntomas existentes
def obtener_sintomas():
    """
    Obtiene todos los síntomas y cuadros almacenados en la base de datos.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT sintoma, cuadro FROM palabras_clave")
            sintomas = cursor.fetchall()
            return sintomas
    except sqlite3.Error as e:
        print(f"Error al obtener los síntomas: {e}")
        return []

# Detección avanzada con OpenAI
def detectar_estado_emocional_con_openai(mensaje):
    """
    Usa OpenAI para detectar emociones o estados psicológicos implícitos en un mensaje.
    """
    try:
        prompt = (
            f"Analiza el siguiente mensaje y detecta emociones o estados psicológicos:\n\n{mensaje}\n\n"
            "Responde con una lista de síntomas o estados emocionales, separados por comas."
        )
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.7
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        print(f"Error al usar OpenAI: {e}")
        return "No se pudo analizar el mensaje."

# Análisis de texto del usuario
def analizar_texto(mensajes_usuario):
    """
    Analiza los mensajes del usuario para detectar coincidencias con los síntomas almacenados
    y usa OpenAI para detectar nuevos estados emocionales.
    """
    palabras_irrelevantes = {
        "un", "una", "el", "la", "lo", "es", "son", "estoy", "siento", "me siento", "tambien", "que", "de", "en", 
        "por", "a", "me", "mi", "tengo", "mucho", "muy"
    }
    saludos_comunes = {"hola", "buenos", "buenas", "saludos", "qué", "tal", "hey", "hola!"}
    
    sintomas = obtener_sintomas()
    if not sintomas:
        return "No se encontraron síntomas para analizar."

    keyword_to_cuadro = {sintoma.lower(): cuadro for sintoma, cuadro in sintomas}
    coincidencias = []
    palabras_detectadas = []

    for mensaje in mensajes_usuario:
        user_words = mensaje.lower().split()
        user_words = [palabra for palabra in user_words if palabra not in saludos_comunes and palabra not in palabras_irrelevantes]
        for palabra in user_words:
            if palabra in keyword_to_cuadro:
                coincidencias.append(keyword_to_cuadro[palabra])
                palabras_detectadas.append(palabra)

    # Detección avanzada con OpenAI para palabras no registradas
    if len(coincidencias) < 2:
        nuevos_estados = detectar_estado_emocional_con_openai(" ".join(mensajes_usuario))
        for estado in nuevos_estados.split(","):
            estado = estado.strip()
            if estado and estado not in keyword_to_cuadro:
                registrar_sintoma(estado, "estado emocional detectado por IA")
                coincidencias.append("estado emocional detectado por IA")
                palabras_detectadas.append(estado)

    if not coincidencias:
        return "No se encontraron suficientes coincidencias para determinar un cuadro psicológico."

    category_counts = Counter(coincidencias)
    cuadro_probable, frecuencia = category_counts.most_common(1)[0]
    probabilidad = (frecuencia / len(coincidencias)) * 100

    return (
        f"En base a los síntomas referidos ({', '.join(set(palabras_detectadas))}), pareciera tratarse de un cuadro relacionado con un {cuadro_probable}. "
        f"Por lo que te sugiero contactar al Lic. Daniel O. Bustamante, un profesional especializado, al WhatsApp +54 911 3310-1186. "
        f"Él podrá ofrecerte una evaluación y un apoyo más completo."
    )

# Manejo de la entrada del usuario con la clase UserInput
def manejar_entrada_usuario(user_input: UserInput):
    """
    Maneja la entrada del usuario, analiza su mensaje y devuelve el resultado.
    """
    mensajes = [user_input.mensaje]  # Convertimos el mensaje a una lista para analizar_texto
    resultado = analizar_texto(mensajes)
    return {"user_id": user_input.user_id, "resultado": resultado}

# Verificar escritura en disco
def verificar_escritura_en_disco():
    """
    Verifica si es posible escribir en el disco persistente.
    """
    try:
        with open(PRUEBA_PATH, "w") as archivo:
            archivo.write("Prueba de escritura exitosa.")
            print("Prueba de escritura exitosa en el disco persistente.")
    except Exception as e:
        print(f"Error al escribir en el disco: {e}")

# Gestión de sesiones (en memoria)
user_sessions = {}
SESSION_TIMEOUT = 60  # Tiempo de inactividad en segundos

@app.on_event("startup")
def startup_event():
    verificar_escritura_en_disco()
    init_db()
    start_session_cleaner()

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

        if user_id not in user_sessions:
            user_sessions[user_id] = {
                "contador_interacciones": 0,
                "ultima_interaccion": time.time(),
                "mensajes": []
            }

        user_sessions[user_id]["ultima_interaccion"] = time.time()
        user_sessions[user_id]["contador_interacciones"] += 1
        user_sessions[user_id]["mensajes"].append(mensaje_usuario)
        interacciones = user_sessions[user_id]["contador_interacciones"]

        if mensaje_usuario == "reiniciar":
            if user_id in user_sessions:
                user_sessions.pop(user_id)
                return {"respuesta": "La conversación ha sido reiniciada. Empezá de nuevo cuando quieras."}
            else:
                return {"respuesta": "No se encontró una sesión activa. Empezá una nueva conversación cuando quieras."}

        if ("contacto" in mensaje_usuario or "numero" in mensaje_usuario or "turno" in mensaje_usuario or "telefono" in mensaje_usuario):
            return {
                "respuesta": (
                    "Para contactar al Lic. Daniel O. Bustamante, te sugiero enviarle un mensaje al WhatsApp "
                    "+54 911 3310-1186. Él podrá responderte a la brevedad."
                )
            }

        if interacciones > 5:
            return {
                "respuesta": (
                    "Si bien debo concluir nuestra conversación, no obstante te sugiero contactar al Lic. Daniel O. Bustamante, un profesional especializado, "
                    "al WhatsApp +54 911 3310-1186. Un saludo."
                )
            }

        if interacciones == 5:
            mensajes = user_sessions[user_id]["mensajes"]
            respuesta_analisis = analizar_texto(mensajes)
            user_sessions[user_id]["mensajes"].clear()
            return {"respuesta": respuesta_analisis}

        prompt = f"Un usuario dice: '{mensaje_usuario}'. Responde de manera profesional y empática."
        respuesta_ai = generar_respuesta_con_openai(prompt)
        return {"respuesta": respuesta_ai}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
