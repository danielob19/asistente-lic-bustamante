import os
import time
import threading
import psycopg2
from psycopg2 import sql
import openai
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from collections import Counter

# Configuración de la clave de API de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("OPENAI_API_KEY no está configurada en las variables de entorno.")

# Configuración de la URL de la base de datos PostgreSQL
DATABASE_URL = "postgresql://my_postgres_db_oahe_user:AItPOENiOHIGPNva0eiCT0kK1od4UhZf@dpg-ctqqj0bqf0us73f4ar1g-a/my_postgres_db_oahe"

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

# Configuración de la base de datos PostgreSQL
def init_db():
    """
    Crea las tablas necesarias si no existen en PostgreSQL.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS palabras_clave (
                id SERIAL PRIMARY KEY,
                sintoma TEXT UNIQUE NOT NULL,
                cuadro TEXT NOT NULL
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interacciones (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                consulta TEXT NOT NULL,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emociones_detectadas (
                id SERIAL PRIMARY KEY,
                emocion TEXT NOT NULL,
                contexto TEXT NOT NULL,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()
        print("Base de datos inicializada en PostgreSQL.")
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")

# Registrar un síntoma
def registrar_sintoma(sintoma: str, cuadro: str):
    """
    Inserta un nuevo síntoma en la base de datos PostgreSQL o lo actualiza si ya existe.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO palabras_clave (sintoma, cuadro) 
            VALUES (%s, %s)
            ON CONFLICT (sintoma) DO NOTHING;
        """, (sintoma, cuadro))
        conn.commit()
        conn.close()
        print(f"Síntoma '{sintoma}' registrado exitosamente con cuadro: {cuadro}.")
    except Exception as e:
        print(f"Error al registrar síntoma '{sintoma}': {e}")

# Registrar una emoción detectada
def registrar_emocion(emocion: str, contexto: str):
    """
    Registra una emoción detectada en la base de datos PostgreSQL.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO emociones_detectadas (emocion, contexto) 
            VALUES (%s, %s);
        """, (emocion, contexto))
        conn.commit()
        conn.close()
        print(f"Emoción '{emocion}' registrada exitosamente con contexto: {contexto}.")
    except Exception as e:
        print(f"Error al registrar emoción '{emocion}': {e}")

# Obtener síntomas existentes
def obtener_sintomas():
    """
    Obtiene todos los síntomas almacenados en la base de datos PostgreSQL.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT sintoma, cuadro FROM palabras_clave")
        sintomas = cursor.fetchall()
        conn.close()
        return sintomas
    except Exception as e:
        print(f"Error al obtener síntomas: {e}")
        return []

# Registrar una interacción
def registrar_interaccion(user_id: str, consulta: str):
    """
    Registra una interacción del usuario en la base de datos PostgreSQL.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO interacciones (user_id, consulta) 
            VALUES (%s, %s);
        """, (user_id, consulta))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error al registrar interacción: {e}")

# Lista de palabras irrelevantes
palabras_irrelevantes = {
    "un", "una", "el", "la", "lo", "es", "son", "estoy", "siento", "me siento", "tambien", "tambien tengo", "que", "de", "en", 
    "por", "a", "me", "mi", "tengo", "mucho", "muy", "un", "poco", "tengo", "animicos", "si", "supuesto", "frecuentes", "verdad", "sé", "hoy", "quiero", 
    "bastante", "mucho", "tambien", "gente", "frecuencia", "entendi", "hola", "estoy", "no", "vos", "entiendo", 
    "buenas", "noches", "soy", "daniel", "mi", "numero", "de", "telefono", "es", "4782-6465", "me", "siento", "para", "mucha", "y", "sufro", "vida", 
    "que", "opinas", "¿","?", "reinicia", "con", "del", "psicologo", "contactarme", "necesito", "lic", "me", "contacto", "número", "gracias", "bustamante", "whatsapp", "bustamane", "das"
}

# Análisis de texto del usuario
def analizar_texto(mensajes_usuario):
    """
    Analiza los mensajes del usuario para detectar coincidencias con los síntomas almacenados
    y muestra un cuadro probable y emociones o patrones de conducta adicionales detectados.
    """
    sintomas_existentes = obtener_sintomas()
    if not sintomas_existentes:
        return "No se encontraron síntomas en la base de datos para analizar."

    keyword_to_cuadro = {sintoma.lower(): cuadro for sintoma, cuadro in sintomas_existentes}
    coincidencias = []
    emociones_detectadas = []
    sintomas_sin_coincidencia = []

    for mensaje in mensajes_usuario:
        user_words = mensaje.lower().split()
        user_words = [palabra for palabra in user_words if palabra not in palabras_irrelevantes]

        for palabra in user_words:
            if palabra in keyword_to_cuadro:
                coincidencias.append(keyword_to_cuadro[palabra])
            else:
                sintomas_sin_coincidencia.append(palabra)

    # Generar emociones detectadas a partir de mensajes sin coincidencia
    if len(coincidencias) < 2:
        texto_usuario = " ".join(mensajes_usuario)
        prompt = (
            f"Analiza el siguiente mensaje y detecta emociones o patrones de conducta humanos implícitos:\n\n"
            f"{texto_usuario}\n\n"
            "Responde con una lista de emociones o patrones de conducta separados por comas."
        )
        try:
            emociones_detectadas = generar_respuesta_con_openai(prompt).split(",")
            emociones_detectadas = [
                emocion.strip().lower() for emocion in emociones_detectadas
                if emocion.strip().lower() not in palabras_irrelevantes
            ]
        except Exception as e:
            print(f"Error al usar OpenAI para detectar emociones: {e}")

    if not coincidencias and not emociones_detectadas:
        return "No se encontraron suficientes coincidencias para determinar un cuadro probable."

    respuesta = ""
    
    if coincidencias:
        category_counts = Counter(coincidencias)
        cuadro_probable, _ = category_counts.most_common(1)[0]
        respuesta = (
            f"Con base en los síntomas detectados ({', '.join(set(coincidencias))}), "
            f"el cuadro probable es: {cuadro_probable}. "
        )

    if emociones_detectadas:
        respuesta += (
            f"Además, notamos emociones o patrones de conducta humanos como {', '.join(set(emociones_detectadas))}, "
            f"por lo que sugiero solicitar una consulta con el Lic. Daniel O. Bustamante escribiendo al WhatsApp "
            f"+54 911 3310-1186 para una evaluación más detallada."
        )

    return respuesta

# Generación de respuestas con OpenAI
def generar_respuesta_con_openai(prompt):
    try:
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
SESSION_TIMEOUT = 60  # Tiempo en segundos para limpiar sesiones inactivas

@app.on_event("startup")
def startup_event():
    init_db()
    # Inicia un hilo para limpiar sesiones inactivas
    start_session_cleaner()

# Función para limpiar sesiones inactivas
def start_session_cleaner():
    """
    Limpia las sesiones inactivas después de un tiempo definido (SESSION_TIMEOUT).
    """
    def cleaner():
        while True:
            current_time = time.time()
            inactive_users = [
                user_id for user_id, session in user_sessions.items()
                if current_time - session["ultima_interaccion"] > SESSION_TIMEOUT
            ]
            for user_id in inactive_users:
                del user_sessions[user_id]
            time.sleep(30)  # Intervalo para revisar las sesiones

    # Ejecutar la limpieza de sesiones en un hilo separado
    thread = threading.Thread(target=cleaner, daemon=True)
    thread.start()

# Comportamiento del Asistente - Endpoint
@app.post("/asistente")
async def asistente(input_data: UserInput):
    try:
        user_id = input_data.user_id
        mensaje_usuario = input_data.mensaje.strip().lower()

        if not mensaje_usuario:
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

        registrar_interaccion(user_id, mensaje_usuario)

        # Inicializa la sesión del usuario si no existe
        if user_id not in user_sessions:
            user_sessions[user_id] = {
                "contador_interacciones": 0,
                "ultima_interaccion": time.time(),
                "mensajes": [],
                "emociones_detectadas": []
            }

        # Actualiza la sesión del usuario
        user_sessions[user_id]["ultima_interaccion"] = time.time()
        user_sessions[user_id]["contador_interacciones"] += 1
        user_sessions[user_id]["mensajes"].append(mensaje_usuario)

        # Comparar con la tabla `palabras_clave`
        sintomas_existentes = obtener_sintomas()
        keyword_to_cuadro = {sintoma.lower(): cuadro for sintoma, cuadro in sintomas_existentes}
        coincidencias = []

        user_words = mensaje_usuario.split()
        for palabra in user_words:
            if palabra in keyword_to_cuadro:
                coincidencias.append(keyword_to_cuadro[palabra])

        # Análisis del estado emocional implícito con OpenAI
        prompt_emocion = (
            f"Analiza el siguiente mensaje del usuario y detecta el estado emocional implícito o sentimientos expresados:\n\n"
            f"{mensaje_usuario}\n\n"
            "Responde con una sola emoción o sentimiento dominante (por ejemplo: tristeza, ansiedad, enojo, etc.)."
        )
        try:
            emocion_detectada = generar_respuesta_con_openai(prompt_emocion)
            emocion_detectada = emocion_detectada.strip().lower()

            if emocion_detectada and emocion_detectada not in user_sessions[user_id]["emociones_detectadas"]:
                user_sessions[user_id]["emociones_detectadas"].append(emocion_detectada)
                registrar_sintoma(emocion_detectada, "emoción detectada automáticamente")
        except Exception as e:
            print(f"Error al analizar emoción con OpenAI: {e}")

        # Respuesta especial en la interacción 6
        if user_sessions[user_id]["contador_interacciones"] == 6:
            if len(coincidencias) >= 2:
                cuadro_probable = Counter(coincidencias).most_common(1)[0][0]
                emociones = ', '.join(set(user_sessions[user_id]["emociones_detectadas"]))
                return {
                    "respuesta": (
                        f"Detecté que tus mensajes reflejan un cuadro probable relacionado con '{cuadro_probable}'. "
                        f"Además, emociones recientes detectadas como: {emociones}. "
                        "Te sugiero contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 para una consulta profesional y detallada. "
                        "Si necesitas, podemos seguir conversando un poco más para explorar más tus emociones."
                    )
                }

        # Continuar con 3 interacciones adicionales si el usuario lo desea
        if 6 < user_sessions[user_id]["contador_interacciones"] < 9:
            return {
                "respuesta": (
                    "Entiendo que podrías necesitar más apoyo para manejar lo que estás sintiendo. "
                    "Estoy aquí para seguir conversando. Recuerda que siempre puedes contactar al Lic. Daniel O. Bustamante al "
                    "WhatsApp +54 911 3310-1186 para una ayuda más personalizada."
                )
            }

        # Respuesta final en la interacción 9
        if user_sessions[user_id]["contador_interacciones"] == 9:
            cuadro_probable = (
                Counter(coincidencias).most_common(1)[0][0]
                if coincidencias
                else "No se pudo determinar un cuadro específico."
            )
            emociones = ', '.join(set(user_sessions[user_id]["emociones_detectadas"]))
            return {
                "respuesta": (
                    f"En base a tus mensajes, detectamos un cuadro probable relacionado con '{cuadro_probable}'. "
                    f"También notamos emociones recientes como: {emociones}. "
                    "Te recomendamos encarecidamente contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 para una consulta detallada. "
                    "Con esto concluimos nuestra conversación. Aguardamos con gusto tu contacto."
                )
            }

        # Respuesta normal si no se alcanzaron condiciones especiales
        prompt = f"Un usuario dice: '{mensaje_usuario}'. Responde de manera profesional y empática."
        respuesta_ai = generar_respuesta_con_openai(prompt)
        return {"respuesta": respuesta_ai}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
