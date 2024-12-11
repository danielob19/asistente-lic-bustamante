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
SESSION_TIMEOUT = 60  # Tiempo de inactividad en segundos

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

# Analizar mensaje del usuario
def analizar_mensaje_usuario(mensaje_usuario: str) -> str:
    """
    Analiza el mensaje del usuario buscando palabras clave en la base de datos,
    identifica categorías asociadas y genera un análisis resumido.
    """
    try:
        # Conectar a la base de datos
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Dividir el mensaje en palabras y buscar coincidencias
        palabras_clave = mensaje_usuario.split()
        consulta = f"""
            SELECT palabra, categoria 
            FROM palabras_clave 
            WHERE palabra IN ({','.join(['?'] * len(palabras_clave))})
        """
        cursor.execute(consulta, palabras_clave)
        resultados = cursor.fetchall()
        conn.close()

        # Si no hay coincidencias
        if not resultados:
            return "No se encontraron coincidencias en la base de datos para los síntomas proporcionados."

        # Agrupar palabras clave por categorías
        categorias = {}
        for palabra, categoria in resultados:
            if categoria not in categorias:
                categorias[categoria] = []
            categorias[categoria].append(palabra)

        # Construir el mensaje basado en las categorías detectadas
        detalles = []
        for categoria, palabras in categorias.items():
            detalles.append(f"{categoria}: {' '.join(palabras)}")

        return "Encontramos coincidencias en las siguientes categorías:\n" + "\n".join(detalles)

    except Exception as e:
        print(f"Error al analizar el mensaje: {e}")
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
                "ultima_interaccion": time.time(),
                "mensajes": [],
                "ultimo_mensaje": None,
            }
        else:
            user_sessions[user_id]["ultima_interaccion"] = time.time()

        # Incrementar contador de interacciones
        user_sessions[user_id]["contador_interacciones"] += 1
        interacciones = user_sessions[user_id]["contador_interacciones"]

        # Almacenar mensaje del usuario
        user_sessions[user_id]["mensajes"].append(mensaje_usuario)

        # Bloquear cualquier interacción después de la quinta
        if interacciones > 5:
            user_sessions.pop(user_id, None)  # Asegurar que la sesión se elimina
            return {
                "respuesta": "Si bien debo finalizar nuestra conversación, igualmente te sugiero"
                "contactar al Lic. Daniel O. Bustamante al whatsapp +54 911 3310-1186 para una mejor evaluación"
                "de tu malestar psicológico y anímico. Si querés reiniciar, escribí **reiniciar**."
            }

        # Reinicio de conversación
        if mensaje_usuario == "reiniciar":
            user_sessions.pop(user_id, None)
            return {"respuesta": "La conversación ha sido reiniciada. Empezá de nuevo cuando quieras escribiendo **reiniciar**."}

        # Manejo de "sí"
        if mensaje_usuario in ["si", "sí", "si claro", "sí claro"]:
            if user_sessions[user_id]["ultimo_mensaje"] in ["si", "sí", "si claro", "sí claro"]:
                return {"respuesta": "Ya confirmaste eso. ¿Hay algo más en lo que pueda ayudarte?"}
            user_sessions[user_id]["ultimo_mensaje"] = mensaje_usuario
            return {"respuesta": "Entendido. ¿Podrías contarme más sobre lo que estás sintiendo?"}

        # Manejo de "no"
        if mensaje_usuario in ["no", "no sé", "tal vez"]:
            return {"respuesta": "Está bien, toma tu tiempo. Estoy aquí para escucharte."}

        # Respuesta durante las primeras interacciones (1 a 4)
        if interacciones < 5:
            respuesta_ai = await interactuar_con_openai(mensaje_usuario)
            return {"respuesta": respuesta_ai}

        # Quinta interacción: análisis completo
        if interacciones == 5:
            sintomas_usuario = " ".join(user_sessions[user_id]["mensajes"])
            resultado_analisis = analizar_mensaje_usuario(sintomas_usuario)
            prompt = (
                f"El usuario compartió los siguientes síntomas: \"{sintomas_usuario}\".\n\n"
                f"Resultado del análisis: {resultado_analisis}\n\n"
                "Redacta una respuesta profesional y empática que mencione los síntomas, posibles cuadros o estados, "
                "y sugiera al usuario contactar al Lic. Daniel O. Bustamante al whatsapp +54 911 3310-1186 para una evaluación "
                "más profunda de su malestar psicológico."
            )
            respuesta_final = await interactuar_con_openai(prompt)
            user_sessions.pop(user_id, None)  # Limpiar la sesión
            return {"respuesta": respuesta_final}

    except Exception as e:
        print(f"Error interno: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# Interacción con OpenAI
async def interactuar_con_openai(mensaje_usuario: str) -> str:
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres un asistente conversacional profesional."},
                {"role": "user", "content": mensaje_usuario}
            ],
            max_tokens=200,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al comunicarse con OpenAI: {str(e)}")
