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
import random

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

# Función para detectar emociones negativas usando OpenAI
def detectar_emociones_negativas(mensaje):
    prompt = (
        f"Analiza el siguiente mensaje y detecta exclusivamente emociones humanas negativas. "
        f"Devuelve una lista separada por comas con las emociones detectadas. "
        f"Si no hay emociones negativas, responde con 'ninguna'.\n\n"
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
        return [emocion.strip() for emocion in emociones.split(",")]

    except Exception as e:
        print(f"Error al detectar emociones negativas: {e}")
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
def registrar_emocion(emocion: str, contexto: str):
    """
    Registra una emoción detectada en la base de datos PostgreSQL.
    Evita insertar duplicados y actualiza el contexto si ya existe.
    """
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO emociones_detectadas (emocion, contexto) 
                    VALUES (%s, %s)
                    ON CONFLICT (emocion) DO UPDATE 
                    SET contexto = EXCLUDED.contexto || '; ' || emociones_detectadas.contexto;
                """, (emocion.strip().lower(), contexto.strip()))
                conn.commit()
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
                "emociones_detectadas": [] # Para almacenar emociones detectadas
            }

        # Actualiza la sesión del usuario
        session = user_sessions[user_id]
        session["ultima_interaccion"] = time.time()

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
        if mensaje_usuario in ["ok", "gracias", "en nada", "en nada mas", "nada mas", "no necesito nada mas", "estoy bien"]:
            return {"respuesta": "Entendido, quedo a tu disposición. Si necesitas algo más, no dudes en decírmelo."}

        # Respuesta específica para saludos simples
        if mensaje_usuario in ["hola", "buenas", "buenos días", "buenas tardes", "buenas noches"]:
            return {"respuesta": "¡Hola! ¿En qué puedo ayudarte hoy?"}

        # 🔹 Manejo de agradecimientos
        agradecimientos = {"gracias", "muy amable", "te agradezco", "muchas gracias", "ok gracias"}
        if mensaje_usuario in agradecimientos:
            return {"respuesta": "De nada, estoy para ayudarte. Que tengas un buen día."}


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
        
        # Incrementa el contador de interacciones
        session["contador_interacciones"] += 1
        session["mensajes"].append(mensaje_usuario)

        contador = session["contador_interacciones"]

        # Respuesta específica para "¿atienden estos casos?"
        if "atienden estos casos" in mensaje_usuario:
            return {
                "respuesta": "Sí, el Lic. Daniel O. Bustamante atiende este tipo de casos. Si necesitas ayuda, no dudes en contactarlo al WhatsApp (+54) 9 11 3310-1186."
            }

        # Proporciona el número de contacto si el usuario lo solicita
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
                "respuesta": (
                    "Para contactar al Lic. Daniel O. Bustamante, puedes enviarle un mensaje al WhatsApp "
                    "+54 911 3310-1186. Él estará encantado de responderte."
                )
            }

         # Proporciona el número de contacto si el usuario lo solicita
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
                "respuesta": (
                    "En mi opinión el Lic. Daniel O. Bustamante, es un excelente epecialista en psicología clínica, seguramente te ayudará, puedes enviarle un mensaje al WhatsApp "
                    "+54 911 3310-1186. Él estará encantado de responderte."
                )
            }


        
        # Manejo para análisis de texto después de 5 interacciones
        if contador == 5:
            mensajes = session["mensajes"]
            emociones_negativas = []

            # Detectar emociones negativas en los mensajes
            for mensaje in mensajes:
                emociones_negativas.extend(detectar_emociones_negativas(mensaje))

            # Registrar emociones en la base de datos
            for emocion in emociones_negativas:
                registrar_emocion(emocion, "interacción 5")

            # Obtener cuadro probable en base a emociones detectadas
            cuadros_probables = [
                cuadro for emocion, cuadro in obtener_sintomas() if emocion in emociones_negativas
            ]
            cuadro_probable = cuadros_probables[0] if cuadros_probables else "no identificado"

            # 🔹 Variaciones en la respuesta (sin pedir más síntomas)
            respuestas_posibles = [
                f"Por lo que mencionaste ({', '.join(emociones_negativas)}), es posible que el cuadro sea {cuadro_probable}. Si querés recibir ayuda profesional, te sugiero contactar al Lic. Daniel O. Bustamante en WhatsApp: +54 911 3310-1186.",
                f"De acuerdo con lo que comentaste ({', '.join(emociones_negativas)}), el cuadro podría ser {cuadro_probable}. Para un análisis más detallado, podés comunicarte con el Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186.",
                f"Lo que describiste ({', '.join(emociones_negativas)}) podría indicar un cuadro relacionado con {cuadro_probable}. Para mayor claridad, te recomiendo hablar con el Lic. Daniel O. Bustamante. Podés escribirle al WhatsApp +54 911 3310-1186.",
                f"Según lo que mencionaste ({', '.join(emociones_negativas)}), podríamos estar ante {cuadro_probable}. Si querés orientación personalizada, te sugiero hablar con el Lic. Daniel O. Bustamante. Su contacto de WhatsApp es +54 911 3310-1186.",
                f"Teniendo en cuenta lo que contaste ({', '.join(emociones_negativas)}), el cuadro probable es {cuadro_probable}. Para recibir una evaluación adecuada, te recomiendo contactar al Lic. Daniel O. Bustamante en WhatsApp: +54 911 3310-1186.",
                f"Considerando tus palabras ({', '.join(emociones_negativas)}), el cuadro podría ser {cuadro_probable}. Si querés una orientación profesional, podés escribir al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186.",
                f"Por lo que has compartido ({', '.join(emociones_negativas)}), el cuadro más probable parece ser {cuadro_probable}. Para hablar con un profesional, podés contactar al Lic. Daniel O. Bustamante en WhatsApp: +54 911 3310-1186.",
                f"Según lo que describiste ({', '.join(emociones_negativas)}), el cuadro probable es {cuadro_probable}. Te sugiero contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 para obtener más información.",
            ]

            # Seleccionar una respuesta aleatoria
            respuesta_variable = random.choice(respuestas_posibles)

            session["mensajes"].clear()
            return {"respuesta": respuesta_variable}


        # Manejo de interacciones 6, 7 y 8
        if 6 <= contador <= 8:
            # 🔹 Verificar si el usuario simplemente agradece
            agradecimientos = {"gracias", "muy amable", "te agradezco", "muchas gracias", "ok gracias"}
    
            if mensaje_usuario in agradecimientos:
                return {"respuesta": "De nada, estoy para ayudarte. Que tengas un buen día."}

            # 🔹 Si el usuario no está agradeciendo, continuar normalmente con la conversación
            ultima_emocion = session["emociones_detectadas"][-1] if session["emociones_detectadas"] else "lo que mencionaste"

            respuestas_posibles = [
                f"Entiendo que sientas {ultima_emocion}. ¿Cómo afecta {ultima_emocion} en tu vida cotidiana?",
                f"A veces {ultima_emocion} puede ser difícil de manejar. ¿Te das cuenta en qué momentos lo sentís con más intensidad?",
                f"Cuando experimentás {ultima_emocion}, ¿cómo impacta en tus relaciones o en tu rutina?",
                f"Comprendo que {ultima_emocion} pueda ser una carga. ¿Hay algo específico que lo detone o lo agrave?",
                f"Sé que {ultima_emocion} no es fácil. ¿Notaste algún patrón en cuándo o cómo aparece?",
                f"Gracias por compartirlo. ¿Cómo describirías el efecto de {ultima_emocion} en tu bienestar general?",
                f"Noté que mencionaste {ultima_emocion}. ¿Te gustaría hablar sobre cómo afrontarlo?",
                f"Cuando sentís {ultima_emocion}, ¿hay algo que hagas para aliviarlo o sentirte mejor?",
                f"Entiendo que {ultima_emocion} puede ser desafiante. ¿Cómo reaccionás ante ello en el día a día?",
                f"A veces, {ultima_emocion} nos hace ver las cosas de una manera particular. ¿Cómo afecta tu perspectiva sobre lo que te rodea?"
            ]
        
            respuesta_variable = random.choice(respuestas_posibles)
            return {"respuesta": respuesta_variable}


        # Manejo para la interacción 9 (igual a la 5, sin pedir más síntomas)
        if contador == 9:
            mensajes = session["mensajes"]
            emociones_negativas = []

            # Detectar emociones negativas en los mensajes
            for mensaje in mensajes:
                emociones_negativas.extend(detectar_emociones_negativas(mensaje))

            # Registrar emociones en la base de datos
            for emocion in emociones_negativas:
                registrar_emocion(emocion, "interacción 9")

            # Obtener cuadro probable en base a emociones detectadas
            cuadros_probables = [
                cuadro for emocion, cuadro in obtener_sintomas() if emocion in emociones_negativas
            ]
            cuadro_probable = cuadros_probables[0] if cuadros_probables else "no identificado"

            # 🔹 Variaciones en la respuesta (sin pedir más síntomas)
            respuestas_posibles = [
                f"Después de analizar lo que mencionaste ({', '.join(emociones_negativas)}), el cuadro probable es {cuadro_probable}. Te sugiero contactar al Lic. Daniel O. Bustamante por WhatsApp al +54 911 3310-1186 para recibir ayuda profesional.",
                f"Por lo que mencionaste ({', '.join(emociones_negativas)}), el cuadro probable es {cuadro_probable}. Si querés hablar con un especialista, podés escribir al Lic. Daniel O. Bustamante en WhatsApp: +54 911 3310-1186.",
                f"Según lo que describiste ({', '.join(emociones_negativas)}), el cuadro probable podría ser {cuadro_probable}. Para recibir orientación profesional, te recomiendo contactar al Lic. Daniel O. Bustamante en WhatsApp: +54 911 3310-1186.",
                f"Teniendo en cuenta lo que me contaste ({', '.join(emociones_negativas)}), parece que el cuadro probable es {cuadro_probable}. Para obtener más ayuda, podés comunicarte con el Lic. Daniel O. Bustamante por WhatsApp al +54 911 3310-1186.",
                f"Por lo que compartiste ({', '.join(emociones_negativas)}), el cuadro probable es {cuadro_probable}. Para hablar con un profesional sobre esto, podés escribir al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186.",
                f"Lo que mencionaste ({', '.join(emociones_negativas)}) parece estar relacionado con {cuadro_probable}. Para recibir asistencia personalizada, te sugiero contactar al Lic. Daniel O. Bustamante en WhatsApp: +54 911 3310-1186.",
                f"En base a lo que describiste ({', '.join(emociones_negativas)}), el cuadro probable es {cuadro_probable}. Para hablar con un profesional, podés contactar al Lic. Daniel O. Bustamante en WhatsApp: +54 911 3310-1186.",
                f"De acuerdo con lo que compartiste ({', '.join(emociones_negativas)}), podríamos estar hablando de {cuadro_probable}. Para obtener un diagnóstico más preciso, te sugiero escribir al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186.",
            ]

            # Seleccionar una respuesta aleatoria
            respuesta_variable = random.choice(respuestas_posibles)

            session["mensajes"].clear()
            return {"respuesta": respuesta_variable}


        # Manejo de interacción 10 (última interacción)
        if contador == 10:
            return {
                "respuesta": (
                    "Hemos llegado al final de nuestra conversación. Para un seguimiento más personalizado, te recomiendo "
                    "contactar al Lic. Daniel O. Bustamante al WhatsApp: +54 911 3310-1186. ¡Gracias por tu tiempo!"
                )
            }

        # Responder con la misma respuesta después de la interacción 10
        if contador > 10:
            return {
                "respuesta": (
                    "Sugiero solicitar una consulta al Lic. Daniel O. Bustamante escribiéndole al WhatsApp "
                    "(+54) 9 11 3310-1186. Aguardamos tu mensaje. ¡Un saludo cordial!"
                )
            }

        # Validar si se detectaron emociones o cuadros antes de generar la respuesta final
        if not session.get("emociones_detectadas") and not session.get("mensajes"):
            return {
                "respuesta": (
                    "No se pudieron identificar emociones claras en tu mensaje. Si sientes que necesitas ayuda, no dudes "
                    "en buscar apoyo profesional o compartir más detalles sobre lo que estás experimentando."
                )
            }

        # Genera una respuesta normal para otros mensajes
        prompt = f"Un usuario dice: '{mensaje_usuario}'. Responde de manera profesional y empática."
        respuesta_ai = generar_respuesta_con_openai(prompt)
        return {"respuesta": respuesta_ai}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


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


# Registrar una emoción detectada
def registrar_emocion(emocion: str, contexto: str):
    """
    Registra una emoción detectada en la base de datos PostgreSQL.
    """
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO emociones_detectadas (emocion, contexto) 
                    VALUES (%s, %s);
                """, (emocion.strip().lower(), contexto.strip()))
                conn.commit()
        print(f"Emoción '{emocion}' registrada exitosamente con contexto: {contexto}.")
    except Exception as e:
        print(f"Error al registrar emoción '{emocion}': {e}")
