import os
import time
import threading
import psycopg2
from psycopg2 import sql
import openai
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
import unicodedata

# Configuración de logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def normalizar_texto(texto: str) -> str:
    """
    Normaliza el texto eliminando acentos y convirtiéndolo a minúsculas.
    """
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto.strip().lower())
        if unicodedata.category(c) != 'Mn'
    )
# Configuración de la clave de API de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("OPENAI_API_KEY no está configurada en las variables de entorno.")

# Configuración de la URL de la base de datos PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL no está configurada en las variables de entorno.")

def conectar_db():
    """
    Establece la conexión con la base de datos PostgreSQL.
    """
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        logger.error(f"Error al conectar con la base de datos: {e}")
        return None

def generar_respuesta_openai(prompt: str, model="gpt-4", max_tokens=150, temperature=0.3) -> str:
    """
    Genera una respuesta usando OpenAI.
    """
    try:
        response = openai.ChatCompletion.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Error en OpenAI: {e}")
        return "Lo siento, hubo un problema al generar una respuesta."
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

# Modelo de datos para las solicitudes del usuario
class UserInput(BaseModel):
    mensaje: str
    user_id: str
def detectar_emociones(mensaje: str) -> list:
    """
    Analiza un mensaje con OpenAI para detectar emociones negativas.
    """
    prompt = f"""
    Analiza el siguiente mensaje y clasifícalo en 'negativo', 'positivo' o 'neutral'.
    Si es negativo, indica las emociones detectadas.
    Mensaje: {mensaje}
    """
    respuesta = generar_respuesta_openai(prompt, max_tokens=50, temperature=0.0)
    return respuesta.split(",") if "negativo" in respuesta else []

def registrar_interaccion(user_id: str, consulta: str):
    """
    Registra una interacción del usuario en la base de datos PostgreSQL.
    """
    try:
        conn = conectar_db()
        if conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO interacciones (user_id, consulta) VALUES (%s, %s);",
                (user_id, consulta)
            )
            conn.commit()
            conn.close()
    except Exception as e:
        logger.error(f"Error al registrar interacción: {e}")

def registrar_emocion(emociones: list, contexto: str):
    """
    Registra emociones detectadas en la base de datos PostgreSQL.
    """
    if not emociones:
        return

    try:
        conn = conectar_db()
        if conn:
            cursor = conn.cursor()
            for emocion in emociones:
                cursor.execute(
                    "INSERT INTO emociones_detectadas (emocion, contexto) VALUES (%s, %s);",
                    (emocion.strip().lower(), contexto.strip())
                )
            conn.commit()
            conn.close()
    except Exception as e:
        logger.error(f"Error al registrar emociones '{', '.join(emociones)}': {e}")
        
@app.post("/asistente")
async def asistente(input_data: UserInput):
    """
    Procesa el mensaje del usuario, detecta emociones y genera una respuesta con OpenAI.
    """
    try:
        user_id = input_data.user_id
        mensaje_usuario = normalizar_texto(input_data.mensaje)

        if not mensaje_usuario:
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

        # Detectar emociones
        emociones_detectadas = detectar_emociones(mensaje_usuario)
        
        # Registrar interacción en la base de datos
        registrar_interaccion(user_id, mensaje_usuario)

        if emociones_detectadas:
            registrar_emocion(emociones_detectadas, mensaje_usuario)
            return {
                "respuesta": f"He detectado emociones negativas: {', '.join(emociones_detectadas)}. ¿Quieres hablar más al respecto?"
            }

        # Generar respuesta con OpenAI
        respuesta_ai = generar_respuesta_openai(mensaje_usuario)
        return {"respuesta": respuesta_ai}

    except Exception as e:
        logger.error(f"Error en asistente: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor.")

@app.get("/status")
def status():
    """
    Endpoint para verificar el estado de la API.
    """
    return {"status": "API en funcionamiento"}
# Gestión de sesiones (en memoria)
user_sessions = {}
SESSION_TIMEOUT = 600  # 10 minutos de inactividad antes de limpiar sesiones

def iniciar_sesion_usuario(user_id: str):
    """
    Inicializa una sesión para el usuario si no existe.
    """
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "contador_interacciones": 0,
            "ultima_interaccion": time.time(),
            "mensajes": []
        }

def actualizar_sesion(user_id: str, mensaje: str):
    """
    Actualiza la sesión del usuario con nuevos mensajes e interacción.
    """
    if user_id in user_sessions:
        session = user_sessions[user_id]
        session["ultima_interaccion"] = time.time()
        session["mensajes"].append(mensaje)
        session["contador_interacciones"] += 1

@app.on_event("startup")

def limpiar_sesiones_inactivas():
    """
    Inicia un hilo que elimina sesiones inactivas después de cierto tiempo.
    """
    thread = threading.Thread(target=_ejecutar_limpieza_sesiones, daemon=True)
    thread.start()

def _ejecutar_limpieza_sesiones():
    """
    Función en segundo plano para limpiar sesiones inactivas.
    """
    while True:
        tiempo_actual = time.time()
        usuarios_inactivos = [
            user_id for user_id, session in user_sessions.items()
            if tiempo_actual - session["ultima_interaccion"] > SESSION_TIMEOUT
        ]
        for user_id in usuarios_inactivos:
            del user_sessions[user_id]
        time.sleep(60)  # Revisar cada minuto

    
def manejar_interaccion_usuario(mensaje_usuario: str, contador: int) -> dict:
    """
    Maneja las interacciones avanzadas, detectando emociones y contexto del usuario.
    """
    mensaje_usuario = normalizar_texto(mensaje_usuario.strip())

    # Detectar emociones
    emociones_negativas = detectar_emociones(mensaje_usuario)

    if emociones_negativas:
        return {
            "respuesta": (
                f"Entiendo que puedas estar sintiendo {', '.join(emociones_negativas)}. "
                "¿Te gustaría contarme más sobre lo que estás experimentando?"
            )
        }

    # Interacción 5: Detección de emociones y cuadro clínico probable
    if contador == 5:
        return manejar_interaccion_5(mensaje_usuario)

    # Interacción 9: Diagnóstico probable basado en interacciones previas
    if contador == 9:
        return manejar_interaccion_9(mensaje_usuario)

    # Manejo de preguntas sobre contacto o especialistas
    if detectar_pregunta_contacto(mensaje_usuario):
        return {"respuesta": "Puedes contactar al Lic. Daniel O. Bustamante -Psicólogo Clínico- enviándole un mensaje al WhatsApp +54 911 3310-1186."}

    # Manejo de frases de cierre
    if mensaje_usuario in ["ok", "gracias", "estoy bien", "nada más"]:
        return {"respuesta": "Entendido, quedo a tu disposición. Si necesitas algo más, no dudes en decírmelo."}

    # Respuesta genérica si no se detectan patrones específicos
    return {"respuesta": generar_respuesta_openai(mensaje_usuario)}

def manejar_interaccion_5(mensaje_usuario: str) -> dict:
    """
    Responde en la 5ª interacción con un análisis más detallado del estado emocional.
    """
    emociones_negativas = detectar_emociones(mensaje_usuario)

    if len(emociones_negativas) < 2:
        return {"respuesta": "Aún no he detectado suficientes indicaciones emocionales. ¿Podrías contarme más sobre cómo te sientes?"}

    return {
        "respuesta": (
            f"He detectado emociones negativas como {', '.join(emociones_negativas)}. "
            "Te recomiendo contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 para una evaluación más detallada."
        )
    }

def manejar_interaccion_9(mensaje_usuario: str) -> dict:
    """
    Responde en la 9ª interacción con un diagnóstico probable basado en emociones detectadas.
    """
    emociones_previas = detectar_emociones(mensaje_usuario)

    if emociones_previas:
        cuadro_probable = determinar_cuadro_probable(emociones_previas)
        return {
            "respuesta": (
                f"En base a tus descripciones y emociones detectadas ({', '.join(emociones_previas)}), "
                f"el cuadro probable es: {cuadro_probable}. Te sugiero contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186."
            )
        }

    return {"respuesta": "Aún no puedo determinar un cuadro claro. ¿Te gustaría contarme más?"}

def detectar_pregunta_contacto(mensaje_usuario: str) -> bool:
    """
    Detecta si el usuario pregunta por contacto, psicólogos o especialistas.
    """
    frases_contacto = [
        "cómo te contacto", "cómo puedo contactarte", "necesito tu número", "quiero comunicarme contigo",
        "whatsapp", "teléfono", "psicólogo", "especialista", "mejor terapeuta"
    ]
    return any(frase in mensaje_usuario for frase in frases_contacto)

def determinar_cuadro_probable(emociones: list) -> str:
    """
    Determina un cuadro clínico probable basado en las emociones detectadas.
    """
    cuadro_probable = "no identificado"
    coincidencias = [cuadro for emocion in emociones if (cuadro := obtener_cuadro_por_emocion(emocion))]
    
    if coincidencias:
        cuadro_probable = max(set(coincidencias), key=coincidencias.count)

    return cuadro_probable

def obtener_cuadro_por_emocion(emocion: str) -> str:
    """
    Obtiene un posible cuadro clínico relacionado con una emoción detectada.
    """
    cuadros = {
        "ansiedad": "Trastorno de Ansiedad Generalizada",
        "tristeza": "Depresión Mayor",
        "estrés": "Trastorno por Estrés Postraumático",
        "desesperanza": "Depresión Clínica",
        "insomnio": "Trastorno del Sueño"
    }
    return cuadros.get(emocion, "no identificado")

DATABASE_URL = "postgresql://my_postgres_db_oahe_user:AItPOENiOHIGPNva0eiCT0kK1od4UhZf@dpg-ctqqj0bqf0us73f4ar1g-a/my_postgres_db_oahe"

def conectar_db():
    """
    Establece la conexión a PostgreSQL directamente.
    """
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        logger.error(f"Error al conectar con la base de datos: {e}")
        return None

def obtener_sintomas():
    """
    Obtiene todos los síntomas almacenados en la base de datos PostgreSQL.
    """
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT sintoma, cuadro FROM palabras_clave")
        sintomas = cursor.fetchall()
        conn.close()
        return sintomas
    except Exception as e:
        logger.error(f"Error al obtener síntomas: {e}")
        return []

def manejar_interaccion_10(user_id: str, mensaje_usuario: str) -> dict:
    """
    En la 10ª interacción, se cierra la conversación y se recomienda una consulta profesional.
    """
    emociones_previas = detectar_emociones(mensaje_usuario)

    if emociones_previas:
        cuadro_probable = determinar_cuadro_probable(emociones_previas)
        return {
            "respuesta": (
                f"Hemos llegado al final de nuestra conversación. Con base en tus emociones detectadas ({', '.join(emociones_previas)}), "
                f"el cuadro probable es: {cuadro_probable}. Te recomiendo encarecidamente contactar al Lic. Daniel O. Bustamante "
                f"al WhatsApp +54 911 3310-1186 para una evaluación más detallada. ¡Gracias por tu tiempo!"
            )
        }

    return {"respuesta": "Hemos llegado al final de nuestra conversación. Si necesitas ayuda, no dudes en buscar apoyo profesional. ¡Gracias por tu tiempo!"}

@app.post("/chat")
async def chat(input_data: UserInput):
    """
    Endpoint principal del asistente: procesa el mensaje del usuario y genera respuestas personalizadas.
    """
    try:
        user_id = input_data.user_id
        mensaje_usuario = normalizar_texto(input_data.mensaje)

        if not mensaje_usuario:
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

        # Inicializa sesión del usuario si es necesario
        iniciar_sesion_usuario(user_id)
        actualizar_sesion(user_id, mensaje_usuario)

        contador = user_sessions[user_id]["contador_interacciones"]

        # Manejo de interacciones clave
        if contador == 5:
            return manejar_interaccion_5(mensaje_usuario)
        if contador == 9:
            return manejar_interaccion_9(mensaje_usuario)
        if contador == 10:
            return manejar_interaccion_10(user_id, mensaje_usuario)

        # Manejo de frases cortas y preguntas
        respuesta_corta = interpretar_respuesta_corta_openai(mensaje_usuario)
        if respuesta_corta:
            return {"respuesta": respuesta_corta}

        # Registro de interacción
        registrar_interaccion(user_id, mensaje_usuario)

        # Respuesta generada con OpenAI
        respuesta_ai = generar_respuesta_openai(mensaje_usuario)
        return {"respuesta": respuesta_ai}

    except Exception as e:
        logger.error(f"Error en chat: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
def registrar_interaccion(user_id: str, consulta: str):
    """
    Registra una interacción del usuario en la base de datos PostgreSQL.
    """
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO interacciones (user_id, consulta) 
            VALUES (%s, %s);
        """, (user_id, consulta))
        conn.commit()
        conn.close()
        logger.info(f"Interacción registrada para el usuario {user_id}: {consulta}")
    except Exception as e:
        logger.error(f"Error al registrar interacción: {e}")


def registrar_sintoma(sintoma: str, cuadro: str):
    """
    Inserta un nuevo síntoma en la base de datos PostgreSQL o lo actualiza si ya existe.
    """
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO palabras_clave (sintoma, cuadro) 
            VALUES (%s, %s)
            ON CONFLICT (sintoma) DO UPDATE SET cuadro = EXCLUDED.cuadro;
        """, (sintoma, cuadro))
        conn.commit()
        conn.close()
        logger.info(f"Síntoma '{sintoma}' registrado con cuadro: {cuadro}.")
    except Exception as e:
        logger.error(f"Error al registrar síntoma '{sintoma}': {e}")


def obtener_cuadro_probable(emociones_detectadas):
    """
    Determina un posible cuadro clínico basado en los síntomas almacenados.
    """
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT sintoma, cuadro FROM palabras_clave")
        sintomas_existentes = cursor.fetchall()
        conn.close()

        keyword_to_cuadro = {sintoma.lower(): cuadro for sintoma, cuadro in sintomas_existentes}

        coincidencias = [keyword_to_cuadro[emocion] for emocion in emociones_detectadas if emocion in keyword_to_cuadro]

        if coincidencias:
            category_counts = Counter(coincidencias)
            cuadro_probable, _ = category_counts.most_common(1)[0]
            return cuadro_probable

        return "no identificado"
    except Exception as e:
        logger.error(f"Error al determinar cuadro probable: {e}")
        return "no identificado"


def detectar_emociones(mensaje):
    """
    Usa OpenAI para analizar emociones en un mensaje y clasificarlas como negativas o neutrales/positivas.
    """
    mensaje = normalizar_texto(mensaje)

    prompt = (
        f"Analiza el siguiente mensaje y detecta emociones humanas. "
        f"Clasifícalas en 'negativas' o 'neutrales/positivas'. "
        f"Devuelve una lista separada por comas con las emociones detectadas y su categoría. "
        f"Si no hay emociones, responde con 'ninguna'.\n\n"
        f"Mensaje: {mensaje}"
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.0
        )
        emociones = response.choices[0].message['content'].strip().lower()

        if emociones == "ninguna":
            return []

        emociones_detectadas = [normalizar_texto(e.strip()) for e in emociones.split(",")]

        return emociones_detectadas
    except Exception as e:
        logger.error(f"Error al detectar emociones: {e}")
        return []
def manejar_interaccion_usuario(mensaje_usuario: str, contador: int) -> dict:
    """
    Maneja las interacciones avanzadas con detección de emociones y consultas.
    """
    mensaje_usuario = normalizar_texto(mensaje_usuario.strip())
    emociones_negativas = detectar_emociones(mensaje_usuario)

    if emociones_negativas:
        return {
            "respuesta": (
                f"Entiendo que puedas estar sintiendo {', '.join(emociones_negativas)}. "
                "¿Te gustaría contarme más sobre lo que estás experimentando?"
            )
        }

    # Interacción 5
    if contador == 5:
        return manejar_interaccion_5(mensaje_usuario)

    # Interacción 9
    if contador == 9:
        return manejar_interaccion_9(mensaje_usuario)

    # Interacción 10 (finalización de conversación)
    if contador == 10:
        return manejar_interaccion_10(mensaje_usuario)

    # Si no hay patrón específico, responder con OpenAI
    return {"respuesta": generar_respuesta_openai(mensaje_usuario)}


@app.on_event("startup")
def startup_event():
    """
    Inicializa la base de datos y limpia sesiones inactivas.
    """
    try:
        conn = conectar_db()
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
        conn.commit()
        conn.close()
        logger.info("Base de datos inicializada.")
    except Exception as e:
        logger.error(f"Error al inicializar la base de datos: {e}")

    limpiar_sesiones_inactivas()


def limpiar_sesiones_inactivas():
    """
    Elimina sesiones de usuario inactivas después de cierto tiempo.
    """
    def limpiar():
        while True:
            tiempo_actual = time.time()
            usuarios_inactivos = [
                user_id for user_id, session in user_sessions.items()
                if tiempo_actual - session["ultima_interaccion"] > SESSION_TIMEOUT
            ]
            for user_id in usuarios_inactivos:
                del user_sessions[user_id]
            time.sleep(60)  # Revisar cada minuto

    thread = threading.Thread(target=limpiar, daemon=True)
    thread.start()
def manejar_interaccion_5(mensaje_usuario: str) -> dict:
    """
    En la 5ª interacción, se genera un análisis emocional más profundo.
    """
    emociones_negativas = detectar_emociones(mensaje_usuario)

    if len(emociones_negativas) < 2:
        return {
            "respuesta": "Aún no he detectado suficientes indicaciones emocionales. ¿Podrías contarme más sobre cómo te sientes?"
        }

    cuadro_probable = obtener_cuadro_probable(emociones_negativas)

    return {
        "respuesta": (
            f"Con base en tus descripciones ({', '.join(emociones_negativas)}), "
            f"el cuadro probable es: {cuadro_probable}. Te recomiendo consultar al Lic. Daniel O. Bustamante "
            f"al WhatsApp +54 911 3310-1186 para una evaluación más detallada."
        )
    }


def manejar_interaccion_9(mensaje_usuario: str) -> dict:
    """
    En la 9ª interacción, se realiza una evaluación final antes de cerrar la conversación.
    """
    emociones_negativas = detectar_emociones(mensaje_usuario)

    if not emociones_negativas:
        return {
            "respuesta": (
                "No se detectaron nuevas emociones en tu mensaje. Si sientes que necesitas ayuda, no dudes en buscar apoyo profesional."
            )
        }

    cuadro_probable = obtener_cuadro_probable(emociones_negativas)

    return {
        "respuesta": (
            f"En base a tus emociones detectadas ({', '.join(emociones_negativas)}), "
            f"el cuadro probable es: {cuadro_probable}. Te sugiero contactar al Lic. Daniel O. Bustamante "
            f"al WhatsApp +54 911 3310-1186 para una evaluación más detallada."
        )
    }
def manejar_interaccion_usuario(mensaje_usuario: str, contador: int) -> dict:
    """
    Maneja todas las interacciones avanzadas.
    """
    emociones_negativas = detectar_emociones(mensaje_usuario)

    if emociones_negativas:
        return {
            "respuesta": (
                f"Entiendo que puedas estar sintiendo {', '.join(emociones_negativas)}. "
                "¿Te gustaría contarme más sobre lo que estás experimentando?"
            )
        }

    if contador == 5:
        return manejar_interaccion_5(mensaje_usuario)

    if contador == 9:
        return manejar_interaccion_9(mensaje_usuario)

    if contador == 10:
        return manejar_interaccion_10(mensaje_usuario)

    return {"respuesta": generar_respuesta_openai(mensaje_usuario)}


def obtener_sintomas():
    """
    Recupera los síntomas almacenados en PostgreSQL.
    """
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT sintoma, cuadro FROM palabras_clave")
        sintomas = cursor.fetchall()
        conn.close()
        return sintomas
    except Exception as e:
        logger.error(f"Error al obtener síntomas: {e}")
        return []


def analizar_texto(mensajes_usuario):
    """
    Analiza los mensajes del usuario y detecta síntomas.
    """
    sintomas_existentes = obtener_sintomas()
    keyword_to_cuadro = {sintoma.lower(): cuadro for sintoma, cuadro in sintomas_existentes}

    coincidencias = []
    for mensaje in mensajes_usuario:
        palabras = mensaje.lower().split()
        coincidencias.extend([keyword_to_cuadro[palabra] for palabra in palabras if palabra in keyword_to_cuadro])

    if coincidencias:
        cuadro_probable = max(set(coincidencias), key=coincidencias.count)
        return f"El cuadro probable basado en tus síntomas es: {cuadro_probable}. Te sugiero consultar a un especialista."

    return "No se encontraron síntomas relevantes en la base de datos."
def registrar_interaccion(user_id: str, consulta: str):
    """
    Registra una interacción en PostgreSQL.
    """
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO interacciones (user_id, consulta) 
            VALUES (%s, %s);
        """, (user_id, consulta))
        conn.commit()
        conn.close()
        logger.info(f"Interacción registrada para el usuario {user_id}: {consulta}")
    except Exception as e:
        logger.error(f"Error al registrar interacción: {e}")


def iniciar_sesion_usuario(user_id):
    """
    Crea una sesión nueva si el usuario no tiene una activa.
    """
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "contador_interacciones": 0,
            "ultima_interaccion": time.time(),
            "mensajes": []
        }


def actualizar_sesion(user_id, mensaje):
    """
    Actualiza la sesión del usuario con un nuevo mensaje.
    """
    session = user_sessions[user_id]
    session["ultima_interaccion"] = time.time()
    session["mensajes"].append(mensaje)
    session["contador_interacciones"] += 1


def limpiar_sesiones_inactivas():
    """
    Elimina sesiones de usuario inactivas después de cierto tiempo.
    """
    def limpiar():
        while True:
            tiempo_actual = time.time()
            usuarios_inactivos = [
                user_id for user_id, session in user_sessions.items()
                if tiempo_actual - session["ultima_interaccion"] > SESSION_TIMEOUT
            ]
            for user_id in usuarios_inactivos:
                del user_sessions[user_id]
            time.sleep(60)  # Revisar cada minuto

    thread = threading.Thread(target=limpiar, daemon=True)
    thread.start()

@app.post("/chat")
async def chat(input_data: UserInput):
    """
    Endpoint principal del asistente.
    """
    try:
        user_id = input_data.user_id
        mensaje_usuario = normalizar_texto(input_data.mensaje)

        if not mensaje_usuario:
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

        iniciar_sesion_usuario(user_id)
        actualizar_sesion(user_id, mensaje_usuario)

        contador = user_sessions[user_id]["contador_interacciones"]

        # Manejo de interacciones clave
        if contador == 5:
            return manejar_interaccion_5(mensaje_usuario)
        if contador == 9:
            return manejar_interaccion_9(mensaje_usuario)
        if contador == 10:
            return manejar_interaccion_10(mensaje_usuario)

        respuesta_corta = interpretar_respuesta_corta_openai(mensaje_usuario)
        if respuesta_corta:
            return {"respuesta": respuesta_corta}

        registrar_interaccion(user_id, mensaje_usuario)

        respuesta_ai = generar_respuesta_openai(mensaje_usuario)
        return {"respuesta": respuesta_ai}

    except Exception as e:
        logger.error(f"Error en chat: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
