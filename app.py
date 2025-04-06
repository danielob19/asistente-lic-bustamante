import os
import time
import threading
import psycopg2
from psycopg2 import sql
import openai
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
import numpy as np
import openai

# 🧠 Lista de preguntas frecuentes (FAQ) y sus respuestas fijas
faq_respuestas = [
    {
        "pregunta": "¿Qué servicios ofrece?",
        "respuesta": (
            "El Lic. Daniel O. Bustamante brinda atención psicológica exclusivamente online, a través de videoconsultas.\n\n"
            "Entre los principales motivos de consulta que aborda se encuentran:\n"
            "- Psicoterapia individual para adultos (modalidad online)\n"
            "- Tratamiento de crisis emocionales\n"
            "- Abordaje de ansiedad, estrés y ataques de pánico\n"
            "- Procesos de duelo y cambios vitales\n"
            "- Estados anímicos depresivos\n"
            "- Problemas de autoestima y motivación\n"
            "- Dificultades vinculares y emocionales\n"
            "- Terapia de pareja online\n\n"
            "Si querés coordinar una consulta o tenés dudas, podés escribirle directamente por WhatsApp al +54 911 3310-1186."
        )
    },
    {
        "pregunta": "¿Cuánto dura la sesión?",
        "respuesta": (
            "Las sesiones con el Lic. Daniel O. Bustamante tienen una duración aproximada de 50 minutos y se realizan por videoconsulta.\n\n"
            "La frecuencia puede variar según cada caso, pero generalmente se recomienda un encuentro semanal para favorecer el proceso terapéutico.\n\n"
            "Si querés coordinar una sesión, podés escribirle por WhatsApp al +54 911 3310-1186."
        )
    },
    {
        "pregunta": "¿Trabaja con obras sociales?",
        "respuesta": (
            "El Lic. Daniel O. Bustamante no trabaja con obras sociales ni prepagas. Atiende únicamente de manera particular. "
            "Si querés coordinar una sesión, podés escribirle al WhatsApp +54 911 3310-1186."
        )
    }
]

# ⚡ Generar embeddings de las preguntas frecuentes (una sola vez al iniciar la app)
def generar_embeddings_faq():
    preguntas = [item["pregunta"] for item in faq_respuestas]
    response = openai.Embedding.create(
        model="text-embedding-ada-002",
        input=preguntas
    )
    for i, embedding in enumerate(response["data"]):
        faq_respuestas[i]["embedding"] = np.array(embedding["embedding"])

from numpy.linalg import norm

def buscar_respuesta_semantica(mensaje: str, umbral=0.88) -> str | None:
    try:
        # Embedding del mensaje del usuario
        embedding_usuario = openai.Embedding.create(
            model="text-embedding-ada-002",
            input=mensaje
        )["data"][0]["embedding"]
        embedding_usuario = np.array(embedding_usuario)

        # Calcular similitud con cada pregunta frecuente
        mejor_score = 0
        mejor_respuesta = None
        for item in faq_respuestas:
            emb_faq = item.get("embedding")
            if emb_faq is not None:
                similitud = np.dot(embedding_usuario, emb_faq) / (norm(embedding_usuario) * norm(emb_faq))
                if similitud > mejor_score and similitud >= umbral:
                    mejor_score = similitud
                    mejor_respuesta = item["respuesta"]

        return mejor_respuesta

    except Exception as e:
        print(f"❌ Error en detección semántica: {e}")
        return None


from pydantic import BaseModel
from collections import Counter
import random
import re

# Configuración de la clave de API de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("OPENAI_API_KEY no está configurada en las variables de entorno.")

# Configuración de la URL de la base de datos PostgreSQL
DATABASE_URL = "postgresql://my_postgres_db_oahe_user:AItPOENiOHIGPNva0eiCT0kK1od4UhZf@dpg-ctqqj0bqf0us73f4ar1g-a/my_postgres_db_oahe"

# Generación de respuestas con OpenAI
def generar_respuesta_con_openai(prompt):
    try:
        print("\n===== DEPURACIÓN - GENERACIÓN DE RESPUESTA CON OPENAI =====")
        print(f"Prompt enviado a OpenAI: {prompt}")

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.3
        )
        
        respuesta = response.choices[0].message['content'].strip()
        print(f"Respuesta generada por OpenAI: {respuesta}\n")
        return respuesta

    except Exception as e:
        print(f"Error al generar respuesta con OpenAI: {e}")
        return "Lo siento, hubo un problema al generar una respuesta. Por favor, intenta nuevamente."

# Función para detectar emociones negativas usando OpenAI
def detectar_emociones_negativas(mensaje):
    prompt = (
        "Analiza el siguiente mensaje y detecta exclusivamente emociones humanas negativas o estados emocionales "
        "relacionados con malestar psicológico. Devuelve una lista separada por comas con las emociones detectadas, "
        "sin texto adicional. **Si el mensaje es ambiguo, devuelve la emoción negativa más cercana en lugar de 'indeterminado'.**\n\n"
        
        "Ejemplos de emociones negativas y estados emocionales:\n"
        "- Tristeza, desesperanza, desolación, impotencia, culpa, vergüenza, frustración, ansiedad, miedo, desamparo, agotamiento.\n"
        "- Expresiones compuestas: 'sensación de abandono', 'temor al rechazo', 'desgaste emocional', 'apatía profunda'.\n\n"
        
        "Reglas de detección:\n"
        "- **Si la emoción es una frase compuesta,** como 'desgaste emocional' o 'tristeza profunda', devuélvela completa.\n"
        "- **Si hay múltiples emociones en el mensaje,** devuélvelas separadas por comas.\n"
        "- **Si no hay emociones negativas claras,** devuelve 'ninguna'.\n\n"
    
        f"Mensaje: {mensaje}"
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.0
        )
        emociones = response.choices[0].message.get("content", "").strip().lower()

        # Mostrar resultado de OpenAI para depuración
        print("\n===== DEPURACIÓN - DETECCIÓN DE EMOCIONES =====")
        print(f"Mensaje analizado: {mensaje}")
        print(f"Respuesta de OpenAI: {emociones}")

        # Limpiar el formato de la respuesta
        emociones = emociones.replace("emociones negativas detectadas:", "").strip()
        emociones = [emocion.strip() for emocion in emociones.split(",") if emocion.strip()]

        # Si OpenAI devuelve "ninguna", retornamos una lista vacía
        if "ninguna" in emociones:
            print("No se detectaron emociones negativas.\n")
            return []

        print(f"Emociones detectadas: {emociones}\n")
        return emociones

    except Exception as e:
        print(f"❌ Error al detectar emociones negativas: {e}")
        return []

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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS faq_similitud_logs (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                consulta TEXT NOT NULL,
                pregunta_faq TEXT NOT NULL,
                similitud FLOAT NOT NULL,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()
        print("Base de datos inicializada en PostgreSQL.")
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")

# Registrar un síntoma con cuadro clínico asignado por OpenAI si no se proporciona
def registrar_sintoma(sintoma: str, cuadro_clinico: str = None):
    """
    Inserta un nuevo síntoma en la base de datos PostgreSQL si no existe.
    Si no se proporciona un cuadro clínico, OpenAI lo asignará automáticamente.
    """

    # Si no se proporciona un cuadro clínico, usar OpenAI para asignarlo
    if cuadro_clinico is None or not cuadro_clinico.strip():
        try:
            prompt_cuadro = (
                f"Asigna un cuadro clínico adecuado a la siguiente emoción: '{sintoma}'.\n\n"
                "Debes identificar y asignar el cuadro clínico más preciso en función de trastornos, síndromes o patrones emocionales. "
                "Si la emoción no corresponde a un cuadro clínico específico, asigna 'Patrón emocional detectado'.\n\n"
                
                "No dejes la respuesta vacía ni respondas con 'indeterminado'. Siempre asigna un cuadro clínico.\n\n"
            
                "Ejemplos de cuadros clínicos válidos:\n"
                "- Trastorno de ansiedad\n"
                "- Depresión mayor\n"
                "- Estrés postraumático\n"
                "- Trastorno de pánico\n"
                "- Baja autoestima\n"
                "- Estado confusional\n"
                "- Desgaste emocional\n"
                "- Trastorno de impulsividad\n"
                "- Insomnio crónico\n"
                "- Desorientación emocional\n"
                "- Sentimientos de aislamiento\n"
                "- Patrón emocional detectado (si no encaja en ningún otro cuadro clínico específico)\n\n"
            
                "Devuelve únicamente el cuadro clínico, sin texto adicional."
            )

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt_cuadro}],
                max_tokens=50,
                temperature=0.0
            )

            cuadro_clinico = response.choices[0].message['content'].strip()

            # Verificar si OpenAI devolvió un cuadro válido
            if not cuadro_clinico:
                print(f"⚠️ OpenAI devolvió un cuadro vacío para '{sintoma}'. Se usará 'Patrón emocional detectado'.")
                cuadro_clinico = "Patrón emocional detectado"

            print(f"🆕 OpenAI asignó el cuadro clínico: {cuadro_clinico} para la emoción '{sintoma}'.")

        except Exception as e:
            print(f"⚠️ Error al obtener cuadro clínico de OpenAI para '{sintoma}': {e}")
            cuadro_clinico = "Patrón emocional detectado"  # Fallback en caso de error

    # Insertar el síntoma con el cuadro clínico en la base de datos
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO palabras_clave (sintoma, cuadro) 
            VALUES (%s, %s)
            ON CONFLICT (sintoma) DO UPDATE SET cuadro = EXCLUDED.cuadro;
        """, (sintoma.strip().lower(), cuadro_clinico))
        conn.commit()
        conn.close()
        print(f"✅ Síntoma '{sintoma}' registrado con cuadro '{cuadro_clinico}'.")
    except Exception as e:
        print(f"❌ Error al registrar síntoma '{sintoma}' en la base de datos: {e}")


# Registrar una emoción detectada en la base de datos
def registrar_emocion(emocion: str, contexto: str):
    """
    Registra una emoción detectada en la base de datos PostgreSQL.
    Evita insertar duplicados y actualiza el contexto si ya existe.
    """
    try:
        print("\n===== DEPURACIÓN - REGISTRO DE EMOCIÓN =====")
        print(f"Intentando registrar emoción: {emocion} | Contexto: {contexto}")

        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cursor:
                # Verificar si la emoción ya existe en la base de datos
                cursor.execute("SELECT contexto FROM emociones_detectadas WHERE emocion = %s;", (emocion.strip().lower(),))
                resultado = cursor.fetchone()

                if resultado:
                    # Si la emoción ya existe, actualizar el contexto
                    nuevo_contexto = f"{resultado[0]}; {contexto.strip()}"
                    cursor.execute("UPDATE emociones_detectadas SET contexto = %s WHERE emocion = %s;", 
                                   (nuevo_contexto, emocion.strip().lower()))
                    print(f"✅ Emoción '{emocion}' ya existe. Contexto actualizado.")
                else:
                    # Si la emoción no existe, insertarla
                    cursor.execute("INSERT INTO emociones_detectadas (emocion, contexto) VALUES (%s, %s);", 
                                   (emocion.strip().lower(), contexto.strip()))
                    print(f"✅ Nueva emoción '{emocion}' registrada en la base de datos.")

                conn.commit()
        print("========================================\n")

    except Exception as e:
        print(f"❌ Error al registrar emoción '{emocion}': {e}")


# Obtener síntomas existentes
def obtener_sintomas_existentes():
    """
    Obtiene todos los síntomas almacenados en la base de datos PostgreSQL y los devuelve como un conjunto en minúsculas.
    Esto mejora la comparación y evita problemas con mayúsculas/minúsculas.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT LOWER(sintoma) FROM palabras_clave")  # Convierte a minúsculas desde la BD
        sintomas = {row[0] for row in cursor.fetchall()}  # Convierte en un conjunto para búsqueda eficiente
        conn.close()
        return sintomas
    except Exception as e:
        print(f"❌ Error al obtener síntomas existentes: {e}")
        return set()

# Registrar una interacción
def registrar_interaccion(user_id: str, consulta: str):
    try:
        print("\n===== DEPURACIÓN - REGISTRO DE INTERACCIÓN =====")
        print(f"Intentando registrar interacción: user_id={user_id}, consulta={consulta}")

        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO interacciones (user_id, consulta) 
            VALUES (%s, %s) RETURNING id;
        """, (user_id, consulta))
        
        interaccion_id = cursor.fetchone()[0]  # Obtener el ID insertado
        conn.commit()
        conn.close()
        
        print(f"✅ Interacción registrada con éxito. ID asignado: {interaccion_id}\n")
        return interaccion_id  # Devolver el ID de la interacción

    except Exception as e:
        print(f"❌ Error al registrar interacción en la base de datos: {e}\n")
        return None

# Registrar una respuesta generada por OpenAI en la base de datos
def registrar_respuesta_openai(interaccion_id: int, respuesta: str):
    """
    Registra la respuesta generada por OpenAI en la base de datos PostgreSQL.
    """
    try:
        print("\n===== DEPURACIÓN - REGISTRO DE RESPUESTA OPENAI =====")
        print(f"Intentando registrar respuesta para interacción ID={interaccion_id}")

        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Verifica si la columna "respuesta" ya existe en la tabla "interacciones"
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'interacciones' AND column_name = 'respuesta';
        """)
        columna_existente = cursor.fetchone()

        if not columna_existente:
            print("⚠️ La columna 'respuesta' no existe en la tabla 'interacciones'. Creándola...")
            cursor.execute("ALTER TABLE interacciones ADD COLUMN respuesta TEXT;")
            conn.commit()

        # Actualiza la interacción con la respuesta generada por OpenAI
        cursor.execute("""
            UPDATE interacciones 
            SET respuesta = %s 
            WHERE id = %s;
        """, (respuesta, interaccion_id))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Respuesta registrada con éxito para interacción ID={interaccion_id}\n")

    except Exception as e:
        print(f"❌ Error al registrar respuesta en la base de datos: {e}\n")


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

# Manejo de respuestas repetitivas
def evitar_repeticion(respuesta, historial):
    respuestas_alternativas = [
        "Entiendo. ¿Podrías contarme más sobre cómo te sientes?",
        "Gracias por compartirlo. ¿Cómo ha sido tu experiencia con esto?",
        "Eso parece importante. ¿Te ha pasado antes?"
    ]
    if respuesta in historial:
        return random.choice(respuestas_alternativas)
    historial.append(respuesta)
    return respuesta

def obtener_coincidencias_sintomas_y_registrar(emociones):
    """
    Busca coincidencias de síntomas en la base de datos y devuelve una lista de cuadros clínicos relacionados.
    Si una emoción no tiene coincidencias exactas ni parciales, la registra en la base de datos para futura clasificación.
    Luego, usa OpenAI para clasificar cualquier síntoma sin cuadro y lo actualiza en la base de datos.
    """
    if not emociones:
        return []

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        print("\n===== DEPURACIÓN SQL =====")
        print("Emociones detectadas:", emociones)

        # Buscar coincidencias exactas en la base de datos
        consulta = "SELECT sintoma, cuadro FROM palabras_clave WHERE sintoma = ANY(%s)"
        cursor.execute(consulta, (emociones,))
        resultados = cursor.fetchall()

        cuadros_probables = [resultado[1] for resultado in resultados]
        sintomas_existentes = [resultado[0] for resultado in resultados]

        print("Síntomas encontrados en la BD:", sintomas_existentes)
        print("Cuadros clínicos encontrados:", cuadros_probables)

        # Identificar emociones que no están en la base de datos y registrarlas sin cuadro clínico
        emociones_nuevas = [emocion for emocion in emociones if emocion not in sintomas_existentes]
        for emocion in emociones_nuevas:
            registrar_sintoma(emocion, None)  # Se registra sin cuadro clínico

        conn.commit()
        conn.close()

        # Ahora clasificamos los síntomas que se registraron sin cuadro clínico
        clasificar_sintomas_sin_cuadro()

        return cuadros_probables if cuadros_probables else []

    except Exception as e:
        print(f"❌ Error al obtener coincidencias de síntomas o registrar nuevos síntomas: {e}")
        return []

def clasificar_sintomas_sin_cuadro():
    """
    Busca síntomas en la base de datos sin un cuadro clínico asignado,
    los clasifica con OpenAI y los actualiza en la base de datos.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        # Obtener síntomas sin cuadro asignado
        cursor.execute("SELECT sintoma FROM palabras_clave WHERE cuadro IS NULL;")
        sintomas_sin_cuadro = [row[0] for row in cursor.fetchall()]
        conn.close()

        if not sintomas_sin_cuadro:
            print("✅ No hay síntomas pendientes de clasificación.")
            return

        print(f"🔍 Clasificando {len(sintomas_sin_cuadro)} síntomas sin cuadro asignado...")

        for sintoma in sintomas_sin_cuadro:
            # Clasificar síntoma con OpenAI
            prompt = f"""
            Dado el síntoma '{sintoma}', clasifícalo dentro de un cuadro psicológico basado en el contexto.
            Algunas opciones pueden ser: "Ansiedad", "Depresión", "Estrés", "Trastorno Fóbico", "Trastorno del sueño", etc.
            Responde solo con el nombre del cuadro sin explicaciones adicionales.
            """

            try:
                respuesta = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=50,
                    temperature=0.0
                )

                cuadro_clinico = respuesta["choices"][0]["message"]["content"].strip()
                print(f"✅ Síntoma '{sintoma}' clasificado como '{cuadro_clinico}'.")

                # Reutilizamos la función existente para registrar el síntoma con su cuadro clínico
                registrar_sintoma(sintoma, cuadro_clinico)

            except Exception as e:
                print(f"⚠️ Error al clasificar síntoma '{sintoma}': {e}")

    except Exception as e:
        print(f"❌ Error al conectar con la base de datos para obtener síntomas sin cuadro: {e}")


@app.post("/asistente")
async def asistente(input_data: UserInput):
    try:
        user_id = input_data.user_id
        mensaje_usuario = input_data.mensaje.strip().lower()

        if not mensaje_usuario:
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

        # Registrar interacción en la base de datos
        registrar_interaccion(user_id, mensaje_usuario)

        # Inicializa la sesión del usuario si no existe
        if user_id not in user_sessions:
            user_sessions[user_id] = {
                "contador_interacciones": 0,
                "ultima_interaccion": time.time(),
                "mensajes": [],
                "emociones_detectadas": [], # Para almacenar emociones detectadas
                "ultimas_respuestas": []
            }

        # Actualiza la sesión del usuario
        session = user_sessions[user_id]
        session["ultima_interaccion"] = time.time()
        session["contador_interacciones"] += 1  # ✅ Incrementar contador aquí
        contador = session["contador_interacciones"]
        session["mensajes"].append(mensaje_usuario)

        # 🔍 Buscar coincidencia semántica en preguntas frecuentes
        respuesta_semantica = buscar_respuesta_semantica(mensaje_usuario)
        if respuesta_semantica:
            # Registrar interacción normalmente, aunque no se detecten emociones
            interaccion_id = registrar_interaccion(user_id, mensaje_usuario)
            registrar_respuesta_openai(interaccion_id, respuesta_semantica)
            return {"respuesta": respuesta_semantica}

        # 🔍 DEPURACIÓN: Mostrar estado actual de la sesión
        print("\n===== DEPURACIÓN - SESIÓN DEL USUARIO =====")
        print(f"Usuario ID: {user_id}")
        print(f"Interacción actual: {contador}")
        print(f"Mensajes en la sesión: {session['mensajes']}")
        print(f"Emociones acumuladas antes del análisis: {session['emociones_detectadas']}")
        print("========================================\n")
        
        # Detectar negaciones o correcciones
        if any(negacion in mensaje_usuario for negacion in ["no dije", "no eso", "no es así", "eso no", "no fue lo que dije"]):
            return {"respuesta": "Entiendo, gracias por aclararlo. ¿Cómo describirías lo que sientes?"}


        # Manejo para "no sé", "ninguna", "ni la menor idea" tras describir un síntoma
        if mensaje_usuario in ["no sé", "ninguna", "ni la menor idea"]:
            # Verificar si ya se alcanzaron suficientes interacciones para un análisis
            if session["contador_interacciones"] >= 9 or session["mensajes"]:
                cuadro_probable = obtener_cuadro_probable(session.get("emociones_detectadas", []))
                emociones_todas = ", ".join(set(session.get("emociones_detectadas", [])[:3]))  # Limitar a 3 emociones

                if not cuadro_probable or cuadro_probable == "no identificado":
                    return {
                        "respuesta": (
                            "Entiendo que no tengas una respuesta clara en este momento. Si sientes que necesitas más ayuda, "
                            "puedes comunicarte con el Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186. Estoy aquí si quieres seguir conversando."
                        )
                    }
                return {
                    "respuesta": (
                        f"Si bien encuentro muy interesante nuestra conversación, debo concluirla. No obstante, en base a los síntomas "
                        f"detectados, el cuadro probable es: {cuadro_probable}. Además, notamos emociones como {emociones_todas}. "
                        f"Te recomiendo contactar al Lic. Daniel O. Bustamante escribiendo al WhatsApp +54 911 3310-1186 para una evaluación "
                        f"más detallada. Un saludo."
                    )
                }

            # Si no hay un análisis previo, responder de manera neutral
            return {"respuesta": "Entendido, quedo a tu disposición. Si necesitas algo más, no dudes en decírmelo."}


        # Manejo para mensajes de cierre (sin insistir ni contabilizar interacciones)
        if mensaje_usuario in ["ok", "gracias", "en nada", "en nada mas", "nada mas", "no necesito nada mas", "estoy bien", "igual"]:
            return {"respuesta": "Entendido, quedo a tu disposición. Si necesitas algo más, no dudes en decírmelo."}

        # Respuesta específica para saludos simples
        if mensaje_usuario in ["hola", "buenas", "buenos días", "buenas tardes", "buenas noches"]:
            return {"respuesta": "¡Hola! ¿En qué puedo ayudarte hoy?"}

        # 🔹 Manejo de agradecimientos
        agradecimientos = {"gracias", "muy amable", "te agradezco", "muchas gracias", "ok gracias"}
        if mensaje_usuario in agradecimientos:
            return {"respuesta": "De nada, estoy para ayudarte. Que tengas un buen día."}

        # Detectar "igual" solo si la última respuesta fue una despedida o agradecimiento
        if mensaje_usuario == "igual" and session["ultimas_respuestas"] and session["ultimas_respuestas"][-1] in mensajes_cierre:
            return {"respuesta": "Entendido, quedo a tu disposición. Si necesitas algo más, no dudes en decírmelo."}

        # 🔹 Manejo de consulta sobre si el Lic. Bustamante atiende estos casos
        if "atienden estos casos" in mensaje_usuario or "atiende casos" in mensaje_usuario or "trata casos" in mensaje_usuario or "atiende temas" in mensaje_usuario or "trata temas" in mensaje_usuario or "atiende problemas" in mensaje_usuario or "trata problemas" in mensaje_usuario or "atiende estos" in mensaje_usuario or "trata estos" in mensaje_usuario or "atiende estos temas" in mensaje_usuario:
            return {
                "respuesta": "Sí, el Lic. Daniel O. Bustamante es un profesional especializado en psicología clínica y está capacitado para atender estos casos. "
                             "Si deseas consultarlo, puedes contactarlo a través de WhatsApp: +54 911 3310-1186."
            }
        
        # 🔹 Proporciona el número de contacto si el usuario lo solicita
        if (
            "contacto" in mensaje_usuario or
            "numero" in mensaje_usuario or
            "número" in mensaje_usuario or
            "turno" in mensaje_usuario or
            "whatsapp" in mensaje_usuario or
            "teléfono" in mensaje_usuario or
            "psicologo" in mensaje_usuario or
            "psicólogo" in mensaje_usuario or
            "terapeuta" in mensaje_usuario or
            "psicoterapia" in mensaje_usuario or
            "terapia" in mensaje_usuario or
            "tratamiento psicológico" in mensaje_usuario or
            "recomendas" in mensaje_usuario or
            "telefono" in mensaje_usuario
        ):
            return {
                "respuesta": "Para contactar al Lic. Daniel O. Bustamante, puedes enviarle un mensaje al WhatsApp +54 911 3310-1186. Él estará encantado de responderte."
            }
        
        # 🔹 Evitar repetir la misma respuesta si ya se dio antes en la sesión
        if "bustamante" in mensaje_usuario or "telefono" in mensaje_usuario or "contacto" in mensaje_usuario:
            if session.get("telefono_mencionado"):
                return {"respuesta": "Si necesitas más información sobre la terapia, dime en qué puedo ayudarte específicamente."}
            
            session["telefono_mencionado"] = True
            return {
                "respuesta": "Para contactar al Lic. Daniel O. Bustamante, puedes enviarle un mensaje al WhatsApp +54 911 3310-1186. Él estará encantado de responderte."
            }
        
        # 🔹 Proporciona el número de contacto si el usuario pregunta por el "mejor psicólogo" o especialista recomendado
        if (
            "especialista" in mensaje_usuario or
            "mejor psicólogo" in mensaje_usuario or
            "mejor psicologo" in mensaje_usuario or
            "mejor terapeuta" in mensaje_usuario or
            "mejor psicoterapeuta" in mensaje_usuario or
            "el mejor" in mensaje_usuario or
            "a quien me recomendas" in mensaje_usuario or
            "que opinas" in mensaje_usuario or
            "qué opinas" in mensaje_usuario or
            "excelente psicólogo" in mensaje_usuario or
            "buen profesional" in mensaje_usuario or
            "que me recomendas" in mensaje_usuario
        ):
            return {
                "respuesta": "En mi opinión, el Lic. Daniel O. Bustamante es un excelente especialista en psicología clínica. Seguramente podrá ayudarte. "
                             "Puedes enviarle un mensaje al WhatsApp +54 911 3310-1186. Él estará encantado de responderte."
            }

        # Manejo para "solo un síntoma y no más" (responder como en la 5ª interacción y finalizar)
        if "no quiero dar más síntomas" in mensaje_usuario or "solo este síntoma" in mensaje_usuario:
            mensajes = session["mensajes"]
            mensajes.append(mensaje_usuario)
            respuesta_analisis = analizar_texto(mensajes)
            session["mensajes"].clear()
            return {
                "respuesta": (
                    f"{respuesta_analisis} Si necesitas un análisis más profundo, también te recomiendo contactar al Lic. Daniel O. Bustamante al WhatsApp "
                    f"+54 911 3310-1186 para una evaluación más detallada."
                )
            }
           
        # Lista de frases que no deben ser analizadas en la detección de emociones
        frases_excluidas = [
            "¿a quién me recomiendas?", "a quién me recomiendas", "me recomendarías a alguien?",
            "qué opinas?", "el atiende estos casos?", "que tipo de casos atienden?"
        ]
        
        # Si el mensaje del usuario está en las frases excluidas, proporcionar respuesta fija
        if mensaje_usuario in frases_excluidas:
            return {
                "respuesta": (
                    "Si buscas una recomendación profesional, te sugiero contactar al Lic. Daniel O. Bustamante. "
                    "Él es un especialista en psicología clínica y puede ayudarte en lo que necesites. "
                    "Puedes escribirle a su WhatsApp: +54 911 3310-1186."
                )
            }
        
        # Excluir "¿A quién me recomiendas?" del análisis de emociones y darle una respuesta fija
        if mensaje_usuario in ["¿a quién me recomiendas?", "a quién me recomiendas"]:
            return {
                "respuesta": (
                    "Si buscas una recomendación profesional, te sugiero contactar al Lic. Daniel O. Bustamante. "
                    "Él es un especialista en psicología clínica y puede ayudarte en lo que necesites. "
                    "Puedes escribirle a su WhatsApp: +54 911 3310-1186."
                )
            }
        
        # 🔍 Asegurar que la lista de emociones está actualizada solo si el mensaje no está en la lista de exclusión
        emociones_detectadas = detectar_emociones_negativas(mensaje_usuario) or []
        
        if not isinstance(emociones_detectadas, list):
            emociones_detectadas = []

        # Obtener la lista de síntomas ya registrados en la BD
        sintomas_existentes = obtener_sintomas_existentes()
        
        # Filtrar emociones detectadas para evitar registrar duplicados
        emociones_nuevas = []
        
        for emocion in emociones_detectadas:
            emocion = emocion.lower().strip()
            
            # Verificar si la emoción ya fue detectada en la sesión para evitar registrar duplicados
            if emocion not in session["emociones_detectadas"]:
                
                # Si la emoción no está en la BD, agregarla a emociones_nuevas y registrar el síntoma
                if emocion not in sintomas_existentes:
                    emociones_nuevas.append(emocion)
                    registrar_sintoma(emocion)  # ✅ Registrar en palabras_clave solo si no existe

        
        # 🔍 Depuración: Mostrar qué emociones se intentarán registrar
        print(f"🔍 Emociones nuevas que intentarán registrarse en palabras_clave: {emociones_nuevas}")
                
        # Registrar solo las emociones nuevas en la base de datos con un cuadro clínico asignado por OpenAI
        for emocion in emociones_nuevas:
            # Generar el prompt para OpenAI
            prompt_cuadro = (
                f"Asigna un cuadro clínico adecuado a la siguiente emoción: '{emocion}'.\n\n"
                "Analiza el síntoma y asigna el cuadro clínico más adecuado en función de trastornos, síndromes o patrones emocionales. "
                "Puedes incluir cualquier cuadro clínico relevante dentro de la psicología, psiquiatría o bienestar emocional, "
                "sin limitarte a una lista fija. Si la emoción no encaja en un cuadro clínico específico, usa 'Patrón emocional detectado'.\n\n"
                
                "Ejemplos de cuadros clínicos válidos:\n"
                "- Trastorno de ansiedad\n"
                "- Depresión mayor\n"
                "- Estrés postraumático\n"
                "- Trastorno de pánico\n"
                "- Baja autoestima\n"
                "- Estado confusional\n"
                "- Desgaste emocional\n"
                "- Trastorno de impulsividad\n"
                "- Insomnio crónico\n"
                "- Desorientación emocional\n"
                "- Sentimientos de aislamiento\n"
                "- Patrón emocional detectado (si no encaja en ningún otro cuadro clínico específico)\n\n"
        
                "Devuelve únicamente el cuadro clínico, sin texto adicional."
            )
        
            try:
                # Llamada a OpenAI para obtener el cuadro clínico
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt_cuadro}],
                    max_tokens=50,
                    temperature=0.0
                )
        
                cuadro_asignado = response.choices[0].message['content'].strip()
        
                # Si OpenAI no devuelve un cuadro válido, asignar un valor por defecto
                if not cuadro_asignado:
                    cuadro_asignado = "Patrón emocional detectado"
        
                # Registrar la emoción con el cuadro clínico asignado
                registrar_sintoma(emocion, cuadro_asignado)
                print(f"🆕 OpenAI asignó el cuadro clínico: {cuadro_asignado} para la emoción '{emocion}'.")
        
            except Exception as e:
                print(f"❌ Error al obtener el cuadro clínico de OpenAI para '{emocion}': {e}")

        
        # 🔍 Confirmación final de emociones registradas
        if emociones_nuevas:
            print(f"✅ Se registraron las siguientes emociones nuevas en palabras_clave: {emociones_nuevas}")
        else:
            print("✅ No hubo emociones nuevas para registrar en palabras_clave.")


        # Evitar agregar duplicados en emociones detectadas
        nuevas_emociones = [e for e in emociones_detectadas if e not in session["emociones_detectadas"]]
        session["emociones_detectadas"].extend(nuevas_emociones)
        
        # 🔍 Verificar si la función recibe correctamente las emociones detectadas
        if session["emociones_detectadas"]:
            print(f"Registrando emociones en la BD: {session['emociones_detectadas']}")
        
            for emocion in session["emociones_detectadas"]:
                registrar_emocion(emocion, f"interacción {session['contador_interacciones']}")

        # Agregar emociones a la sesión sin causar errores
        session["emociones_detectadas"].extend(emociones_detectadas)
        
        # Evaluación de emociones y cuadro probable en la interacción 5 y 9
        if contador in [5, 9]:
            emociones_detectadas = detectar_emociones_negativas(" ".join(session["mensajes"]))
            
            # Evitar agregar duplicados en emociones detectadas
            nuevas_emociones = [e for e in emociones_detectadas if e not in session["emociones_detectadas"]]
            session["emociones_detectadas"].extend(nuevas_emociones)
        
            # 🔍 DEPURACIÓN: Mostrar emociones detectadas
            print("\n===== DEPURACIÓN - INTERACCIÓN 5 o 9 =====")
            print(f"Interacción: {contador}")
            print(f"Mensaje del usuario: {mensaje_usuario}")
            print(f"Emociones detectadas en esta interacción: {emociones_detectadas}")
            print(f"Emociones acumuladas hasta ahora: {session['emociones_detectadas']}")
        
            # Buscar coincidencias en la base de datos para determinar el cuadro probable
            coincidencias_sintomas = obtener_coincidencias_sintomas_y_registrar(session["emociones_detectadas"])
        
            # 🔍 DEPURACIÓN: Mostrar síntomas encontrados en la BD
            print(f"Coincidencias encontradas en la BD: {coincidencias_sintomas}")
        
            if len(coincidencias_sintomas) >= 2:
                cuadro_probable = Counter(coincidencias_sintomas).most_common(1)[0][0]
            else:
                cuadro_probable = "No se pudo determinar un cuadro probable con suficiente precisión."
        
            # 🔍 DEPURACIÓN: Mostrar cuadro probable determinado
            print(f"Cuadro probable determinado: {cuadro_probable}")
            print("========================================\n")
        
            respuesta = (
                f"Con base en los síntomas detectados ({', '.join(set(coincidencias_sintomas))}), "
                f"el cuadro probable es: {cuadro_probable}. Te sugiero considerar una consulta con el Lic. Daniel O. Bustamante "
                f"escribiendo al WhatsApp +54 911 3310-1186 para obtener una evaluación más detallada."
            )
        
            if contador == 9:
                respuesta += (
                    " Además, he encontrado interesante nuestra conversación, pero para profundizar más en el análisis de tu malestar, "
                    "sería ideal que consultes con un profesional. Por ello, te sugiero que te contactes con el Lic. Bustamante. "
                    "Lamentablemente, no puedo continuar con la conversación más allá de este punto."
                )
        
            session["mensajes"].clear()  # Limpiar mensajes después del análisis
            return {"respuesta": respuesta}
        
        # 🔹 A partir de la interacción 10, solo recomendar la consulta profesional
        if contador >= 10:
            respuestas_repetitivas = [
                "Te sugiero contactar al Lic. Daniel O. Bustamante al WhatsApp: +54 911 3310-1186 para recibir ayuda profesional.",
                "Para obtener una evaluación más detallada, te recomiendo contactar al Lic. Bustamante en WhatsApp: +54 911 3310-1186.",
                "No puedo continuar con esta conversación, pero el Lic. Bustamante puede ayudarte. Contáctalo en WhatsApp: +54 911 3310-1186.",
                "Es importante que recibas ayuda profesional. El Lic. Bustamante está disponible en WhatsApp: +54 911 3310-1186."
            ]
            return {"respuesta": random.choice(respuestas_repetitivas)}
            

        # 🔹 Consultas sobre obras sociales, prepagas o asistencia psicológica
        preguntas_cobertura = [
            r"(atiende[n|s]?|trabaja[n|s]?|acepta[n|s]?|tom[a|ás]|toma[n]?|atiendo)\s+(por|con)?\s*(osde|swiss medical|galeno|prepaga|obra social|cobertura médica|asistencia psicológica)",
            r"(osde|swiss medical|galeno|prepaga|obra social|cobertura médica|asistencia psicológica)\s+.*(cubren|incluye|incluyen|puedo usar|sirve|vale|acepta|aceptan|trabaja|trabajan|atiende|atienden)",
            r"(puedo|quiero|necesito).*(usar|utilizar).*(osde|swiss medical|galeno|prepaga|obra social)",
            r"(cubren|cubre|acepta|aceptás|aceptan|trabaja|trabajás|trabajan|atiende|atendés|atienden).*?(osde|swiss medical|galeno|prepaga|obra social)"
        ]
        
        for patron in preguntas_cobertura:
            if re.search(patron, mensaje_usuario):
                return {
                    "respuesta": (
                        "El Lic. Daniel O. Bustamante no trabaja con obras sociales ni prepagas. "
                        "Atiende únicamente de manera particular. Si querés coordinar una sesión, podés escribirle al WhatsApp +54 911 3310-1186."
                    )
                }
        
        # 🔹 Consultas sobre precios, honorarios o valor de la sesión
        if any(palabra in mensaje_usuario for palabra in [
            "precio", "cuánto sale", "cuánto cuesta", "valor", "honorario", "cobra", "cobrás", "tarifa", "cuánto cobra", "cuanto cobra", "cuánto es"
        ]):
            return {
                "respuesta": (
                    "El valor de la sesión puede depender del tipo de consulta. "
                    "Para conocer el costo exacto, te recomiendo escribirle directamente al Lic. Bustamante al WhatsApp +54 911 3310-1186."
                )
            } 

        # 🔹 Consultas sobre los servicios psicológicos que ofrece
        consultas_servicios = [
            "qué servicios ofrece", "qué servicios brinda", "qué trata", "con qué trabaja", "en qué temas trabaja",
            "qué tipo de terapias hace", "qué tipo de terapia ofrece", "qué temas aborda", "qué puede tratar",
            "cuáles son sus especialidades", "qué tipo de atención brinda", "qué problemas trata", "qué áreas trabaja",
            "temas que trata", "qué trata bustamante", "qué hace el licenciado", "qué atiende", "motivos de consulta",
            "problemas que atiende", "en qué puede ayudarme"
        ]
        
        if any(frase in mensaje_usuario for frase in consultas_servicios):
            return {
                "respuesta": (
                    "El Lic. Daniel O. Bustamante brinda atención psicológica exclusivamente online, a través de videoconsultas.\n\n"
                    "Entre los principales motivos de consulta que aborda se encuentran:\n"
                    "- Psicoterapia individual para adultos (modalidad online)\n"
                    "- Tratamiento de crisis emocionales\n"
                    "- Abordaje de ansiedad, estrés y ataques de pánico\n"
                    "- Procesos de duelo y cambios vitales\n"
                    "- Estados anímicos depresivos\n"
                    "- Problemas de autoestima y motivación\n"
                    "- Dificultades vinculares y emocionales\n"
                    "- Terapia de pareja online\n\n"
                    "Si querés coordinar una consulta o tenés dudas, podés escribirle directamente por WhatsApp al +54 911 3310-1186."
                )
            }

        # 🔹 Consultas sobre duración o frecuencia de las sesiones
        consultas_duracion_frecuencia = [
            "cuánto dura", "cuanto dura", "duración de la sesión", "dura la sesión", "cuánto tiempo", "cuánto tiempo duran", 
            "cada cuánto", "frecuencia", "con qué frecuencia", "cuántas veces", "cuántas sesiones", "cada cuánto tiempo",
            "cuánto duran las sesiones", "duración sesión", "sesión dura"
        ]
        
        if any(frase in mensaje_usuario for frase in consultas_duracion_frecuencia):
            return {
                "respuesta": (
                    "Las sesiones con el Lic. Daniel O. Bustamante tienen una duración aproximada de 50 minutos y se realizan por videoconsulta.\n\n"
                    "La frecuencia puede variar según cada caso, pero generalmente se recomienda un encuentro semanal para favorecer el proceso terapéutico.\n\n"
                    "Si querés coordinar una sesión o resolver alguna duda, podés escribirle directamente por WhatsApp al +54 911 3310-1186."
                )
            }
            
        # 🔹 Consultas sobre formas de pago, precios o modalidad de pago
        consultas_pago = [
            "cómo se paga", "formas de pago", "medios de pago", "se puede pagar", "puedo pagar", "pago", "se abona", 
            "cómo abono", "cómo es el pago", "modalidad de pago", "se paga por sesión", "pagar con", "cómo pagar"
        ]
        
        if any(frase in mensaje_usuario for frase in consultas_pago):
            return {
                "respuesta": (
                    "El Lic. Daniel O. Bustamante trabaja con modalidad de pago particular.\n\n"
                    "Para coordinar una sesión y consultar los medios de pago disponibles, podés escribirle directamente por WhatsApp al +54 911 3310-1186."
                )
            }

        
        
        # 🔹 Generar respuesta con OpenAI si no es la interacción 5, 9 o 10+
        prompt = (
            f"Un usuario pregunta: '{mensaje_usuario}'. "
            "Respondé como si fueras el asistente personal del Lic. Daniel O. Bustamante. "
            "Mantené un tono profesional, claro y empático. "
            "Evitá usar términos institucionales como 'nosotros', 'nuestro equipo', 'nuestra institución', etc. "
            "Referite a él como 'el Licenciado', 'el profesional', o 'el Lic. Bustamante', según corresponda. "
            "Él es psicólogo clínico. No brindes información sobre servicios financieros, legales o técnicos. "
            "Si el usuario desea contactarlo, proporcioná directamente su número de WhatsApp: +54 911 3310-1186."
        )
        
        # Obtener respuesta de OpenAI
        respuesta_ai = generar_respuesta_con_openai(prompt)
        
        # 🔍 Filtro para lenguaje institucional
        palabras_prohibidas = ["nosotros", "nuestro equipo", "nuestra institución", "desde nuestra", "trabajamos en conjunto"]
        if any(palabra in respuesta_ai.lower() for palabra in palabras_prohibidas):
            respuesta_ai = (
                "Gracias por tu consulta. El Lic. Daniel O. Bustamante estará encantado de ayudarte. "
                "Podés escribirle directamente al WhatsApp +54 911 3310-1186 para obtener más información."
            )
        
        # 🔍 Filtro para desvíos temáticos (por si OpenAI habla de finanzas o cosas raras)
        temas_prohibidos = ["finanzas", "inversiones", "educación financiera", "consultoría financiera", "legal", "técnico"]
        if any(tema in respuesta_ai.lower() for tema in temas_prohibidos):
            respuesta_ai = (
                "El Lic. Daniel O. Bustamante es psicólogo clínico. Si querés saber más sobre los servicios que ofrece, "
                "podés escribirle directamente por WhatsApp al +54 911 3310-1186 y te brindará toda la información necesaria."
            )
        
        # 🔍 Reemplazo de marcador si quedó en la respuesta
        respuesta_ai = respuesta_ai.replace("[Incluir número de contacto]", "+54 911 3310-1186")
        
        # Registrar respuesta generada por OpenAI
        interaccion_id = registrar_interaccion(user_id, mensaje_usuario)
        registrar_respuesta_openai(interaccion_id, respuesta_ai)
        
        return {"respuesta": respuesta_ai}

        
        # 🔹 Registrar la respuesta generada por OpenAI en la base de datos
        interaccion_id = registrar_interaccion(user_id, mensaje_usuario)  # Asegurarse de obtener el ID de la interacción
        registrar_respuesta_openai(interaccion_id, respuesta_ai)
        
        # 🔹 Registrar la respuesta generada por OpenAI en la base de datos
        registrar_respuesta_openai(contador, respuesta_ai)
        
        return {"respuesta": respuesta_ai}

        # 🔹 BLOQUE 1: Evita repetir "Hasta ahora mencionaste..." en cada respuesta
        if emociones_detectadas:
            emociones_unicas = list(set(emociones_detectadas))  # Elimina duplicados en esta detección
        
            # Verificar si hay emociones nuevas que aún no se han mencionado en las últimas 5 interacciones
            emociones_nuevas = [e for e in emociones_unicas if e not in session["emociones_detectadas"][-5:]]
        
            # Si hay emociones nuevas, agregarlas con control
            if emociones_nuevas:
                session["emociones_detectadas"].extend(emociones_nuevas)
                
                # Limitar almacenamiento a un máximo de 10 emociones recientes
                session["emociones_detectadas"] = session["emociones_detectadas"][-10:]
        
                return {
                    "respuesta": (
                        f"Entiendo que puedes estar sintiéndote {' y '.join(emociones_nuevas)}. "
                        "Si deseas hablar más al respecto, estoy aquí para escucharte."
                    )
                }
        
        # 🔹 BLOQUE 2: Listar emociones sin repeticiones y evitar respuesta robótica
        emociones_unicas = list(set(session["emociones_detectadas"]))
        
        # Construcción de una respuesta más natural dependiendo del contexto
        if emociones_unicas:
            respuesta_emocional = f"Hasta ahora has mencionado emociones como {' y '.join(emociones_unicas)}. "
            respuesta_emocional += "Si necesitas hablar sobre ello, dime en qué puedo ayudarte."
        
            return {"respuesta": respuesta_emocional}


        # Generar una respuesta variada
        respuestas_variadas = [
            "Entiendo, cuéntame más sobre eso.",
            "¿Cómo te hace sentir esto en tu día a día?",
            "Eso parece difícil. ¿Cómo te afecta?",
            "Gracias por compartirlo. ¿Quieres hablar más sobre eso?",
        ]

        # Solo generar respuesta variada si no se detectaron emociones o cuadros probables
        if not session.get("emociones_detectadas") and not session.get("mensajes"):
            respuesta_variable = random.choice(respuestas_variadas)
            return {"respuesta": evitar_repeticion(respuesta_variable, session["ultimas_respuestas"])}
        
        # Genera una respuesta normal para otros mensajes
        prompt = f"Un usuario dice: '{mensaje_usuario}'. Responde de manera profesional y empática."
        respuesta_ai = generar_respuesta_con_openai(prompt)
        
        # 🔹 Registrar la respuesta generada por OpenAI en la base de datos
        interaccion_id = registrar_interaccion(user_id, mensaje_usuario)  # Asegurarse de obtener el ID de la interacción
        registrar_respuesta_openai(interaccion_id, respuesta_ai)
        
        return {"respuesta": respuesta_ai}
        
        # Obtener cuadro probable si hay al menos 2 coincidencias de síntomas en la base de datos
        coincidencias_sintomas = obtener_coincidencias_sintomas(emociones_unicas)
        cuadro_probable = obtener_cuadro_probable(emociones_unicas) if len(coincidencias_sintomas) >= 2 else "No se pudo determinar un cuadro probable con suficiente precisión."
        
        # Registrar emociones en la base de datos solo si son nuevas
        for emocion in emociones_unicas:
            registrar_emocion(emocion, f"interacción {contador}")
        
        # 🔹 Manejo de interacciones 6, 7 y 8
        if 6 <= contador <= 8:
            # Si el usuario agradece, se cierra la conversación educadamente
            agradecimientos = {"gracias", "muy amable", "te agradezco", "muchas gracias", "ok gracias"}
            if mensaje_usuario in agradecimientos:
                return {"respuesta": "De nada, estoy para ayudarte. Que tengas un buen día."}
        
            # Si el usuario sigue expresando malestar
            ultima_emocion = session["emociones_detectadas"][-1] if session["emociones_detectadas"] else None
        
            if not ultima_emocion:
                return {
                    "respuesta": "Te noto preocupado. ¿Cómo afecta esto a tu día a día?"
                }
        
            # 🔹 Variaciones en la respuesta
            respuestas_posibles = [
                f"Comprendo que sentir {ultima_emocion} no es fácil. ¿Cómo te afecta en tu rutina diaria?",
                f"A veces, {ultima_emocion} puede hacer que todo parezca más difícil. ¿Hay algo que te ayude a sobrellevarlo?",
                f"Cuando experimentás {ultima_emocion}, ¿sentís que hay situaciones o personas que lo empeoran o lo alivian?",
                f"Sé que {ultima_emocion} puede ser agotador. ¿Cómo influye en tu estado de ánimo general?",
                f"Gracias por compartirlo. ¿Notaste algún cambio en la intensidad de {ultima_emocion} con el tiempo?",
                f"Cuando te sentís {ultima_emocion}, ¿hay algo que hagas para tratar de sentirte mejor?",
                f"Experimentar {ultima_emocion} puede ser difícil. ¿Notaste algún patrón en cuándo suele aparecer?",
                f"Entiendo que {ultima_emocion} no es fácil de manejar. ¿Te gustaría hablar sobre qué te ha ayudado en el pasado?",
                f"Cuando mencionaste {ultima_emocion}, pensé en cómo puede afectar el bienestar general. ¿Cómo lo sentís hoy en comparación con otros días?",
                f"A veces, {ultima_emocion} nos hace ver las cosas de una manera distinta. ¿Cómo ha influido en tu percepción de lo que te rodea?"
            ]
        
            # Seleccionar una respuesta aleatoria
            respuesta_variable = random.choice(respuestas_posibles)
            return {"respuesta": respuesta_variable}


        # Manejo de interacción 10 (última interacción)
        if contador == 10:
            respuestas_finales = [
                "Hemos llegado al final de nuestra conversación. Para un seguimiento más personalizado, te recomiendo contactar al Lic. Daniel O. Bustamante al WhatsApp: +54 911 3310-1186. ¡Gracias por tu tiempo!",
                "Espero que esta conversación te haya sido útil. Si querés hablar con un profesional, podés comunicarte con el Lic. Daniel O. Bustamante al WhatsApp: +54 911 3310-1186.",
                "Fue un placer charlar contigo. Si necesitás más orientación, te sugiero contactar al Lic. Daniel O. Bustamante en WhatsApp: +54 911 3310-1186.",
                "Gracias por compartir lo que estás sintiendo. Para una atención más personalizada, te recomiendo hablar con el Lic. Daniel O. Bustamante. Podés escribirle al WhatsApp: +54 911 3310-1186.",
                "Hemos concluido nuestra conversación. Si querés seguir hablando con un profesional, te sugiero contactar al Lic. Daniel O. Bustamante en WhatsApp: +54 911 3310-1186.",
                "Si sentís que necesitás apoyo adicional, lo mejor es consultar con un especialista. Podés comunicarte con el Lic. Daniel O. Bustamante a través de WhatsApp: +54 911 3310-1186.",
                "Espero que esta conversación te haya ayudado. Si querés una consulta más detallada, podés escribir al Lic. Daniel O. Bustamante en WhatsApp: +54 911 3310-1186.",
                "Fue un gusto hablar contigo. Para cualquier consulta adicional, te recomiendo contactar al Lic. Daniel O. Bustamante a través de WhatsApp: +54 911 3310-1186."
            ]
        
            respuesta_variable = random.choice(respuestas_finales)
            return {"respuesta": respuesta_variable}
        
        # Frases de cierre que indican que el usuario ya entendió y está finalizando la conversación
        frases_cierre = [
            "gracias", "muchas gracias", "ok gracias", "ok", "igualmente", "si si entendí", 
            "lo haré mañana", "mañana lo llamo", "gracias por tu atención"
        ]
        
        # Manejo de interacciones posteriores a la 10
        if contador >= 10:
            # Si el usuario menciona una frase de cierre, responder educadamente sin insistir
            if any(frase in mensaje_usuario.lower() for frase in frases_cierre):
                respuestas_cierre = [
                    "Me alegra saberlo. Si necesitas algo más, estaré aquí.",
                    "Espero que todo vaya bien para ti. Te deseo lo mejor.",
                    "Si alguna vez necesitas hablar de nuevo, estaré disponible. Cuídate.",
                    "Estoy aquí si en el futuro necesitas hablar. Cuídate mucho."
                ]
                return {"respuesta": random.choice(respuestas_cierre)}
        
            # Respuesta estándar de recomendación, pero sin repetir demasiado
            respuestas_repetitivas = [
                "Si deseas continuar con una evaluación más detallada, puedes contactar al Lic. Bustamante en WhatsApp: +54 911 3310-1186.",
                "No dudes en buscar apoyo profesional. Te sugiero comunicarte con el Lic. Bustamante en WhatsApp: +54 911 3310-1186.",
                "Si crees que necesitas más ayuda, podrías consultar al Lic. Bustamante en WhatsApp: +54 911 3310-1186."
            ]
            return {"respuesta": random.choice(respuestas_repetitivas)}

        
        # Validar si se detectaron emociones o cuadros antes de generar la respuesta final
        if not session.get("emociones_detectadas") and not session.get("mensajes"):
            return {
                "respuesta": (
                    "No se pudieron identificar emociones claras en tu mensaje. Si sientes que necesitas ayuda, no dudes "
                    "en buscar apoyo profesional o compartir más detalles sobre lo que estás experimentando."
                )
            }
        
        
        # Definir respuestas_variadas antes de usarla
        respuestas_variadas = [
            "Entiendo, cuéntame más sobre eso.",
            "¿Cómo te hace sentir esto en tu día a día?",
            "Eso parece difícil. ¿Cómo te afecta?",
            "Gracias por compartirlo. ¿Quieres hablar más sobre eso?",
        ]
        
        # Ahora sí, usar respuestas_variadas sin errores
        respuesta_variable = random.choice(respuestas_variadas)
        return {"respuesta": evitar_repeticion(respuesta_variable, session["ultimas_respuestas"])}
        
    except Exception as e:  # ✅ Capturar errores que ocurran dentro del try
        print(f"Error en la función asistente: {e}")
        return {"respuesta": "Lo siento, ocurrió un error al procesar tu solicitud. Intenta de nuevo."}
      

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

