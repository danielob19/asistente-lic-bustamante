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

# Configuración de la base de datos SQLite
def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS palabras_clave (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sintoma TEXT UNIQUE NOT NULL,
                cuadro TEXT NOT NULL
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

# Actualizar estructura de la base de datos
def actualizar_estructura_bd():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(palabras_clave)")
        columnas = cursor.fetchall()
        nombres_columnas = [columna[1] for columna in columnas]

        if "palabra" in nombres_columnas and "categoria" in nombres_columnas:
            cursor.execute("ALTER TABLE palabras_clave RENAME TO palabras_clave_old")
            
            cursor.execute("""
                CREATE TABLE palabras_clave (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sintoma TEXT UNIQUE NOT NULL,
                    cuadro TEXT NOT NULL
                )
            """)
            
            cursor.execute("""
                INSERT INTO palabras_clave (sintoma, cuadro)
                SELECT palabra, categoria FROM palabras_clave_old
            """)
            
            cursor.execute("DROP TABLE palabras_clave_old")
            print("Estructura de la base de datos actualizada exitosamente.")

        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"Error al actualizar la estructura de la base de datos: {e}")

# Registrar síntoma nuevo
def registrar_sintoma(sintoma: str, cuadro: str):
    """
    Inserta un nuevo síntoma en la base de datos o lo actualiza si ya existe.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO palabras_clave (sintoma, cuadro) VALUES (?, ?)", (sintoma, cuadro))
        conn.commit()
        if cursor.rowcount > 0:
            print(f"Síntoma '{sintoma}' registrado exitosamente con cuadro: {cuadro}.")
        else:
            print(f"Síntoma '{sintoma}' ya existe y no se modificó.")
        conn.close()
    except Exception as e:
        print(f"Error al registrar síntoma '{sintoma}': {e}")

# Obtener síntomas existentes
def obtener_sintomas():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT sintoma, cuadro FROM palabras_clave")
        sintomas = cursor.fetchall()
        conn.close()
        return sintomas
    except Exception as e:
        print(f"Error al obtener síntomas: {e}")
        return []

# Inspeccionar la base de datos
def inspeccionar_base_de_datos():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(palabras_clave)")
        estructura = cursor.fetchall()
        conn.close()
        print("Estructura de la tabla 'palabras_clave':")
        for columna in estructura:
            print(columna)
    except Exception as e:
        print(f"Error al inspeccionar la base de datos: {e}")

# Lista de palabras irrelevantes
palabras_irrelevantes = {
    "un", "una", "el", "la", "lo", "es", "son", "estoy", "siento", "me siento", "tambien", "tambien tengo", "que", "de", "en", 
    "por", "a", "me", "mi", "tengo", "mucho", "muy", "un", "poco", "tengo", "animicos", "si", "supuesto", "frecuentes", "verdad", "sé", "hoy", "quiero", 
    "bastante", "mucho", "tambien", "gente", "frecuencia", "entendi", "hola", "estoy", "no", "entiendo", 
    "buenas", "noches", "soy", "daniel", "mi", "numero", "de", "telefono", "es", "4782-6465", "me", "siento", 
    "que", "opinas", "?"
}

# Análisis de texto del usuario
def analizar_texto(mensajes_usuario):
    """
    Analiza los mensajes del usuario para detectar coincidencias con los síntomas almacenados
    y muestra un cuadro probable y síntomas adicionales detectados.
    """
    saludos_comunes = {"hola", "buenos", "buenas", "saludos", "qué", "tal", "hey", "hola!"}
    sintomas_existentes = obtener_sintomas()
    if not sintomas_existentes:
        return "No se encontraron síntomas en la base de datos para analizar."

    keyword_to_cuadro = {sintoma.lower(): cuadro for sintoma, cuadro in sintomas_existentes}
    coincidencias = []
    sintomas_detectados = []
    sintomas_sin_coincidencia = []

    for mensaje in mensajes_usuario:
        user_words = mensaje.lower().split()
        user_words = [palabra for palabra in user_words if palabra not in saludos_comunes]
        user_words = [palabra for palabra in user_words if palabra not in palabras_irrelevantes]

        for palabra in user_words:
            if palabra in keyword_to_cuadro:
                coincidencias.append(keyword_to_cuadro[palabra])
                sintomas_detectados.append(palabra)
            else:
                sintomas_sin_coincidencia.append(palabra)

    if len(coincidencias) < 2:
        texto_usuario = " ".join(mensajes_usuario)
        prompt = (
            f"Analiza el siguiente mensaje y detecta emociones o estados psicológicos implícitos:\n\n"
            f"{texto_usuario}\n\n"
            "Responde con una lista de emociones o estados emocionales separados por comas."
        )
        try:
            emociones_detectadas = generar_respuesta_con_openai(prompt).split(",")
            for emocion in emociones_detectadas:
                emocion = emocion.strip().lower()
                if emocion and emocion not in keyword_to_cuadro:
                    registrar_sintoma(emocion, "estado emocional detectado por IA")
                    coincidencias.append("estado emocional detectado por IA")
                    sintomas_detectados.append(emocion)
        except Exception as e:
            print(f"Error al usar OpenAI para detectar emociones: {e}")

    if not coincidencias:
        return "No se encontraron suficientes coincidencias para determinar un cuadro probable."

    category_counts = Counter(coincidencias)
    cuadro_probable, _ = category_counts.most_common(1)[0]

    respuesta = (
        f"Con base en los síntomas detectados ({', '.join(set(sintomas_detectados))}), "
        f"el cuadro probable es: {cuadro_probable}. "
    )

    if sintomas_sin_coincidencia:
        respuesta += (
            f"Además, notamos síntomas de {', '.join(set(sintomas_sin_coincidencia))}, "
            f"por lo que sugiero solicitar una consulta con el Lic. Daniel O. Bustamante escribiendo al WhatsApp "
            f"+54 911 3310-1186 para una evaluación más detallada."
        )

    return respuesta

# Generación de respuestas con OpenAI
def generar_respuesta_con_openai(prompt):
    try:
        prompt = f"{prompt}\nResponde de manera profesional, pero directa y objetiva."
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.6
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        print(f"Error al generar respuesta con OpenAI: {e}")
        return "Lo siento, hubo un problema al generar una respuesta. Por favor, intenta nuevamente."

# Clase para solicitudes del usuario
class UserInput(BaseModel):
    mensaje: str
    user_id: str

# Gestión de sesiones (en memoria)
user_sessions = {}
SESSION_TIMEOUT = 60

@app.on_event("startup")
def startup_event():
    verificar_escritura_en_disco()
    init_db()
    actualizar_estructura_bd()
    inspeccionar_base_de_datos()
    start_session_cleaner()

# Verificar escritura en disco
def verificar_escritura_en_disco():
    try:
        with open(PRUEBA_PATH, "w") as archivo:
            archivo.write("Prueba de escritura exitosa.")
        print("Prueba de escritura en disco exitosa.")
    except Exception as e:
        print(f"Error al escribir en el disco: {e}")

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
    thread.start
