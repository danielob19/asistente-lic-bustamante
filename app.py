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
import logging
import unicodedata

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def normalizar_texto(texto):
    """
    Normaliza el texto eliminando acentos y convirtiéndolo a minúsculas.
    """
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto.lower())
        if unicodedata.category(c) != 'Mn'
    )

# Configuración de la clave de API de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("OPENAI_API_KEY no está configurada en las variables de entorno.")

# Configuración de la URL de la base de datos PostgreSQL
DATABASE_URL = "postgresql://my_postgres_db_oahe_user:AItPOENiOHIGPNva0eiCT0kK1od4UhZf@dpg-ctqqj0bqf0us73f4ar1g-a/my_postgres_db_oahe"

# Generación de respuestas con OpenAI
def generar_respuesta_con_openai(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.3
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        print(f"Error al generar respuesta con OpenAI: {e}")
        return "Lo siento, hubo un problema al generar una respuesta. Por favor, intenta nuevamente."

# Manejo de frases de confirmación o cierre
def interpretar_respuesta_corta(mensaje):
    """
    Interpreta mensajes cortos como 'no no', 'ok ok', 'ahh ok ok', etc.,
    y responde de manera acorde al contexto.
    """
    mensaje = mensaje.strip().lower()
    # Conjunto de frases comunes para cierres o confirmaciones
    frases_cierre = {"ok", "ok ok", "ahh ok", "ahh ok ok", "gracias", "nada más", "gracias por todo", "todo bien", "estoy bien", "no no", "no no ok"}
    if mensaje in frases_cierre:
        return "Entendido, quedo a tu disposición. ¿Algo más en lo que pueda ayudarte?"
    return None  # Si no es una frase de cierre, no responde aquí

# Función para detectar emociones negativas usando OpenAI y Registro
def detectar_emociones(mensaje):
    """
    Usa OpenAI para analizar emociones en un mensaje y clasificarlas como negativas o neutrales/positivas.
    Registra automáticamente las emociones negativas en la base de datos.
    """
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
            return [], []
        
        emociones_detectadas = [e.strip() for e in emociones.split(",")]
        emociones_negativas = [e for e in emociones_detectadas if "negativa" in e]
        emociones_neutrales_positivas = [e for e in emociones_detectadas if "neutro" in e or "positivo" in e]
        
        # Registrar solo emociones negativas en la base de datos
        if emociones_negativas:
            registrar_emocion(emociones_negativas, mensaje)
        
        return emociones_negativas, emociones_neutrales_positivas
    except Exception as e:
        print(f"Error al detectar emociones: {e}")
        return [], []

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
            ON CONFLICT (sintoma) DO UPDATE SET cuadro = EXCLUDED.cuadro;
        """, (sintoma, cuadro))
        conn.commit()
        conn.close()
        print(f"Síntoma '{sintoma}' registrado exitosamente con cuadro: {cuadro}.")
    except Exception as e:
        print(f"Error al registrar síntoma '{sintoma}': {e}")

# Registrar una emoción detectada
# Esta función analiza el mensaje para detectar emociones negativas usando OpenAI.
# Registra automáticamente cada emoción detectada en la base de datos llamando a `registrar_emocion`.
def registrar_emocion(emociones, contexto):
    """
    Registra una o varias emociones detectadas en la base de datos PostgreSQL.
    """
    if not emociones:
        return  # No hay emociones que registrar

    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cursor:
                for emocion in emociones:
                    cursor.execute("""
                        INSERT INTO emociones_detectadas (emocion, contexto) 
                        VALUES (%s, %s)
                        ON CONFLICT (emocion) DO NOTHING;
                    """, (emocion.strip().lower(), contexto.strip()))
                conn.commit()
        print(f"Emociones registradas exitosamente: {', '.join(emociones)} con contexto: {contexto}.")
    except Exception as e:
        print(f"Error al registrar emociones '{', '.join(emociones)}': {e}")

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
    "bastante", "mucho", "tambien", "gente", "frecuencia", "entendi", "hola", "estoy", "vos", "entiendo", 
    "soy", "mi", "de", "es", "4782-6465", "me", "siento", "para", "mucha", "y", "sufro", "vida", 
    "que", "opinas", "¿","?", "reinicia", "con", "del", "necesito", "me", "das"
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

    # Procesar mensajes del usuario para detectar síntomas
    for mensaje in mensajes:
        user_words = mensaje.lower().split()
        # Filtrar palabras irrelevantes y descartar palabras cortas (como "se", "las")
        user_words = [
            palabra for palabra in user_words
            if palabra not in palabras_irrelevantes and len(palabra) > 2 and palabra.isalpha()
        ]

        for palabra in user_words:
            if palabra in keyword_to_cuadro:
                coincidencias.append(keyword_to_cuadro[palabra])
            elif palabra not in nuevos_sintomas:
                nuevos_sintomas.append(palabra)


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

            # Registrar cada emoción detectada como síntoma en la base de datos
            for emocion in emociones_detectadas:
                registrar_sintoma(emocion, "patrón emocional detectado")

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

@app.post("/asistente")
async def asistente(input_data: UserInput):
    try:
        user_id = input_data.user_id
        mensaje_usuario = normalizar_texto(input_data.mensaje.strip())  # 🔹 Aplicamos normalización

        if not mensaje_usuario:
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

        # 🔹 **Primero, preguntamos a OpenAI si el usuario está pidiendo el contacto**
        prompt_detectar = [
            {"role": "system", "content": (
                "Eres un asistente que analiza si el usuario está pidiendo un número de contacto. "
                "Si el usuario pregunta por un número de teléfono, WhatsApp o contacto, responde EXACTAMENTE con 'SOLICITUD_CONTACTO'. "
                "Si no lo está pidiendo, responde EXACTAMENTE con 'NINGUNA'. "
                "No agregues explicaciones, solo devuelve 'SOLICITUD_CONTACTO' o 'NINGUNA'."
            )},
            {"role": "user", "content": mensaje_usuario}
        ]


        response_detectar = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=prompt_detectar,
            max_tokens=5,
            temperature=0.0
        )

        decision_ai = response_detectar.choices[0].message['content'].strip().upper()

        # 🔹 **Si OpenAI detecta que el usuario está pidiendo un contacto, damos la respuesta directamente**
        if "SOLICITUD_CONTACTO" in decision_ai:
            return {"respuesta": "Puedes contactar al Lic. Daniel O. Bustamante a través de WhatsApp: +54 911 3310-1186."}


        # 🔹 **Inicializar sesión del usuario si no existe**
        if user_id not in user_sessions:
            user_sessions[user_id] = {
                "historial": [],
                "ultima_interaccion": time.time()
            }

        session = user_sessions[user_id]
        session["ultima_interaccion"] = time.time()  # Actualizar última interacción

        # Contexto de la conversación (últimos 5 mensajes)
        historial = session["historial"][-5:]

        # 🔹 **Instrucciones para OpenAI para la conversación normal**
        prompt_conversacion = [
            {"role": "system", "content": (
                "Eres un asistente profesional especializado en psicología. "
                "Responde de manera empática y profesional a cualquier mensaje. "
                "Si el usuario pregunta por un número de contacto, responde con 'SOLICITUD_CONTACTO'. "
                "De lo contrario, responde normalmente."
            )}

        ]
        prompt_conversacion.extend(historial)
        prompt_conversacion.append({"role": "user", "content": mensaje_usuario})

        # 🔹 **Enviar el mensaje a OpenAI SOLO SI NO ES UNA SOLICITUD DE CONTACTO**
        response_conversacion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=prompt_conversacion,
            max_tokens=150,
            temperature=0.3
        )

        respuesta_ai = response_conversacion.choices[0].message['content'].strip()

        # 🔹 **Actualizar historial de conversación**
        session["historial"].append({"role": "user", "content": mensaje_usuario})
        session["historial"].append({"role": "assistant", "content": respuesta_ai})

        # Limitar historial a 10 mensajes para no sobrecargar memoria
        session["historial"] = session["historial"][-10:]

        # 🔹 **Buscar emociones negativas en la respuesta de OpenAI**
        emociones_negativas, _ = detectar_emociones(respuesta_ai)
        if emociones_negativas:
            registrar_emocion(emociones_negativas, mensaje_usuario)

        return {"respuesta": respuesta_ai}

    except Exception as e:
        logger.error(f"Error en /asistente: {e}")
        raise HTTPException(status_code=500, detail="Error interno en el servidor")



def manejar_interaccion_usuario(mensaje_usuario, contador):
    """
    Mejora la continuidad de la conversación y la detección de contexto en preguntas específicas.
    """
    import logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)

    mensaje_usuario = normalizar_texto(mensaje_usuario.strip())
    
    # Detección de emociones con OpenAI
    emociones_negativas, emociones_neutrales_positivas = detectar_emociones(mensaje_usuario)
    
    if emociones_negativas:
        return {"respuesta": f"He detectado estas emociones negativas: {', '.join(emociones_negativas)}. Si necesitas apoyo, no dudes en contactarme directamente para que podamos conversar más a fondo."}
    
    if emociones_neutrales_positivas:
        return {"respuesta": f"He detectado estas emociones: {', '.join(emociones_neutrales_positivas)}. ¡Estoy aquí para ayudarte en lo que necesites!"}
    
    # Interacción 5 y 9: Mencionar emociones y cuadro clínico probable
    if contador in [5, 9]:
        cuadro_probable = "no identificado"  # Aquí puedes incluir lógica para detectar cuadros clínicos
        respuesta = ""
        if emociones_negativas:
            respuesta += f"He detectado estas emociones negativas: {', '.join(emociones_negativas)}. "
        respuesta += f"El cuadro clínico probable es: {cuadro_probable}. "
        respuesta += "Si necesitas apoyo, no dudes en contactarme directamente para que podamos conversar más a fondo."
        return {"respuesta": respuesta}
    

    # Cierre profesional después de la décima interacción
    if contador >= 10:
        return {"respuesta": "Hemos llegado a un punto donde es recomendable continuar la conversación de manera más personal. Te sugiero contactarme directamente para seguir conversando. ¡Gracias por tu tiempo!"}
    
    # Si no hay coincidencia, responder de forma genérica en lugar de devolver None
    logger.warning(f"No se encontró coincidencia en manejar_interaccion_usuario para el mensaje: '{mensaje_usuario}'")
    return {"respuesta": "Lo siento, no entendí bien tu consulta. ¿Podrías reformularla?"}

def analizar_emociones_y_patrones(mensajes, emociones_acumuladas):
    """
    Detecta emociones y patrones de conducta en los mensajes, buscando coincidencias en la tabla `palabras_clave`.
    Si no hay coincidencias, usa OpenAI para detectar emociones negativas y las registra en la base de datos.
    """
    try:
        # Obtener síntomas almacenados en la tabla `palabras_clave`
        sintomas_existentes = obtener_sintomas()
        keyword_to_cuadro = {sintoma.lower(): cuadro for sintoma, cuadro in sintomas_existentes}
        emociones_detectadas = []

        # Buscar coincidencias en la tabla `palabras_clave`
        for mensaje in mensajes:
            user_words = mensaje.lower().split()
            user_words = [palabra for palabra in user_words if palabra not in palabras_irrelevantes]

            for palabra in user_words:
                if palabra in keyword_to_cuadro:
                    emociones_detectadas.append(keyword_to_cuadro[palabra])

        # Si no hay coincidencias, usar OpenAI para detectar emociones negativas
        if not emociones_detectadas:
            texto_usuario = " ".join(mensajes)
            prompt = (
                f"Analiza el siguiente mensaje y detecta emociones negativas o patrones emocionales humanos. "
                f"Si no hay emociones claras, responde 'emociones ambiguas'.\n\n"
                f"{texto_usuario}\n\n"
                "Responde con una lista de emociones negativas separadas por comas."
            )
            emociones_detectadas = generar_respuesta_con_openai(prompt).split(",")
            emociones_detectadas = [
                emocion.strip().lower() for emocion in emociones_detectadas
                if emocion.strip().lower() not in palabras_irrelevantes
            ]

            # Registrar nuevas emociones en la base de datos
            for emocion in emociones_detectadas:
                registrar_emocion(emocion, texto_usuario)

        return emociones_detectadas

    except Exception as e:
        print(f"Error al analizar emociones y patrones: {e}")
        return []
