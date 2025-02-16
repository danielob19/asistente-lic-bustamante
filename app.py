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
        f"Devuelve una lista separada por comas con las emociones detectadas, sin texto adicional. "
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

        # Limpiar el formato de la respuesta
        emociones = emociones.replace("emociones negativas detectadas:", "").strip()
        emociones = [emocion.strip() for emocion in emociones.split(",") if emocion.strip()]

        if "ninguna" in emociones:
            return []
        return emociones

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

# Registrar una emoción detectada
def registrar_emocion(emocion: str, contexto: str):
    """
    Registra una emoción detectada en la base de datos PostgreSQL.
    Evita insertar duplicados y actualiza el contexto si ya existe.
    """
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cursor:
                # Verificar si la emoción ya existe
                cursor.execute("SELECT contexto FROM emociones_detectadas WHERE emocion = %s;", (emocion.strip().lower(),))
                resultado = cursor.fetchone()

                if resultado:
                    # Si la emoción ya existe, actualizar el contexto
                    nuevo_contexto = resultado[0] + "; " + contexto.strip()
                    cursor.execute("UPDATE emociones_detectadas SET contexto = %s WHERE emocion = %s;", 
                                   (nuevo_contexto, emocion.strip().lower()))
                else:
                    # Si la emoción no existe, insertarla
                    cursor.execute("INSERT INTO emociones_detectadas (emocion, contexto) VALUES (%s, %s);", 
                                   (emocion.strip().lower(), contexto.strip()))

                conn.commit()
        print(f"Emoción '{emocion}' registrada o actualizada con contexto: {contexto}.")
    except Exception as e:
        print(f"Error al registrar emoción '{emocion}': {e}")

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

# Obtener coincidencias de síntomas en la base de datos y registrar nuevas emociones
def obtener_coincidencias_sintomas_y_registrar(emociones):
    if not emociones:
        return []
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Buscar coincidencias en la base de datos con ILIKE para permitir coincidencias parciales
        consulta = "SELECT sintoma, cuadro FROM palabras_clave WHERE " + " OR ".join(["sintoma ILIKE %s" for _ in emociones])
        cursor.execute(consulta, [f"%{emocion}%" for emocion in emociones])
        resultados = cursor.fetchall()
        
        cuadros_probables = [resultado[1] for resultado in resultados]
        sintomas_existentes = [resultado[0] for resultado in resultados]
        
        # Identificar emociones que no están en la base de datos y registrarlas
        emociones_nuevas = [emocion for emocion in emociones if emocion not in sintomas_existentes]
        for emocion in emociones_nuevas:
            cursor.execute("INSERT INTO palabras_clave (sintoma, cuadro) VALUES (%s, NULL)", (emocion,))
        
        conn.commit()
        conn.close()
        
        return cuadros_probables if cuadros_probables else []
    
    except Exception as e:
        print(f"Error al obtener coincidencias de síntomas o registrar nuevos síntomas: {e}")
        return []

@app.post("/asistente")
async def asistente(input_data: UserInput):
    try:
        user_id = input_data.user_id
        mensaje_usuario = input_data.mensaje.strip().lower()

        if not mensaje_usuario:
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

        # Registrar interacción en la base de datos
        registrar_interaccion(user_id, mensaje_usuario)

        # Registrar sesión del usuario si no existe
        if user_id not in user_sessions:
            user_sessions[user_id] = {
                "contador_interacciones": 0,
                "ultima_interaccion": time.time(),
                "mensajes": [],
                "emociones_detectadas": []
            }

        session = user_sessions[user_id]
        session["ultima_interaccion"] = time.time()
        session["contador_interacciones"] += 1
        contador = session["contador_interacciones"]
        session["mensajes"].append(mensaje_usuario)

        print(f"Interacción {contador}: {mensaje_usuario}")
        print(f"Emociones acumuladas antes del análisis: {session['emociones_detectadas']}")

        # Actualiza la sesión del usuario
        session = user_sessions[user_id]
        session["ultima_interaccion"] = time.time()
        
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
        
        # Asegurar que la lista de emociones está actualizada
        emociones_detectadas = detectar_emociones_negativas(mensaje_usuario) or []
        
        if not isinstance(emociones_detectadas, list):
            emociones_detectadas = []
        
        # Agregar emociones a la sesión sin causar errores
        session["emociones_detectadas"].extend(emociones_detectadas)
        
        # Evaluación de emociones y cuadro probable en la interacción 5 y 9
        if contador in [5, 9]:
            emociones_detectadas = detectar_emociones_negativas(" ".join(session["mensajes"]))
            
            # Evitar agregar duplicados en emociones detectadas
            nuevas_emociones = [e for e in emociones_detectadas if e not in session["emociones_detectadas"]]
            session["emociones_detectadas"].extend(nuevas_emociones)
        
            # Mostrar en consola para depuración
            print(f"Interacción {contador}: {mensaje_usuario}")
            print(f"Emociones detectadas en esta interacción: {emociones_detectadas}")
            print(f"Emociones acumuladas después del análisis: {session['emociones_detectadas']}")
        
            # Buscar coincidencias en la base de datos para determinar el cuadro probable
            coincidencias_sintomas = obtener_coincidencias_sintomas(session["emociones_detectadas"])
            
            # Depuración: Verificar qué síntomas devuelve la base de datos
            print(f"Coincidencias de síntomas en la BD para emociones {session['emociones_detectadas']}: {coincidencias_sintomas}")
            
            if len(coincidencias_sintomas) >= 2:
                cuadro_probable = Counter(coincidencias_sintomas).most_common(1)[0][0]
            else:
                cuadro_probable = "No se pudo determinar un cuadro probable con suficiente precisión."

        
            # Construcción de la respuesta con emociones y cuadro probable
            respuesta = (
                f"Detecté emociones negativas como: {', '.join(set(session['emociones_detectadas']))}. "
                f"Basado en esto, el cuadro probable es: {cuadro_probable}. "
                f"Si deseas más orientación, te recomiendo contactar al Lic. Daniel O. Bustamante en WhatsApp: +54 911 3310-1186."
            )
        
            session["mensajes"].clear()  # Limpiar mensajes después del análisis
            return {"respuesta": respuesta}


        # Generar una respuesta empática con OpenAI si no se detecta otro tipo de respuesta
        respuesta_ai = generar_respuesta_con_openai(f"Un usuario dice: '{mensaje_usuario}'. Responde de manera profesional y empática.")
        return {"respuesta": respuesta_ai}
        
        # Agregar emociones a la sesión sin causar errores
        session["emociones_detectadas"].extend(emociones_detectadas)
        
        
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

        # Evitar repetir la misma respuesta si ya se dio antes en la sesión
        if "bustamante" in mensaje_usuario or "telefono" in mensaje_usuario or "contacto" in mensaje_usuario:
            if session.get("telefono_mencionado"):
                return {"respuesta": "Si necesitas más información sobre la terapia, dime en qué puedo ayudarte específicamente."}
            
            session["telefono_mencionado"] = True
            return {"respuesta": "Para contactar al Lic. Daniel O. Bustamante, puedes enviarle un mensaje al WhatsApp +54 911 3310-1186. Él estará encantado de responderte."}


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

        # Evita repetir "Hasta ahora mencionaste..." en cada respuesta
        if emociones_detectadas:
            emociones_unicas = list(set(emociones_detectadas))
            
            # Verificar si la emoción es nueva y aún no ha sido mencionada recientemente
            emociones_nuevas = [e for e in emociones_unicas if e not in session["emociones_detectadas"][-3:]]
        
            # Si hay emociones nuevas, pero sin repetir la confirmación constante
            if emociones_nuevas:
                session["emociones_detectadas"].extend(emociones_nuevas)
                return {
                    "respuesta": (
                        f"Entiendo que puedes estar sintiéndote {' y '.join(emociones_nuevas)}. "
                        "Si deseas hablar más al respecto, estoy aquí para escucharte."
                    )
                }


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
        return {"respuesta": respuesta_ai}
        
        # OpenAI siempre detecta emociones negativas antes de decidir si registrarlas
        emociones_detectadas = detectar_emociones_negativas(mensaje_usuario)
        session["emociones_detectadas"].extend(emociones_detectadas)
        
        # Listar emociones únicas detectadas
        emociones_unicas = list(set(session["emociones_detectadas"]))
        
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
        
        # Manejo de interacciones posteriores a la 10
        if contador > 10:
            respuestas_repetitivas = [
                "Sugiero solicitar una consulta al Lic. Daniel O. Bustamante escribiéndole al WhatsApp (+54) 9 11 3310-1186. Aguardamos tu mensaje. ¡Un saludo cordial!",
                "Para una consulta más personalizada, te sugiero escribir al Lic. Daniel O. Bustamante en WhatsApp: +54 911 3310-1186.",
                "Si querés recibir más orientación, podés contactar al Lic. Daniel O. Bustamante en WhatsApp: +54 911 3310-1186.",
                "Si necesitás más ayuda, te recomiendo comunicarte con el Lic. Daniel O. Bustamante por WhatsApp: +54 911 3310-1186.",
                "No dudes en hablar con un profesional. Podés escribir al Lic. Daniel O. Bustamante en WhatsApp: +54 911 3310-1186.",
                "Si querés continuar con una evaluación más detallada, podés escribir al Lic. Daniel O. Bustamante en WhatsApp: +54 911 3310-1186."
            ]
        
            respuesta_variable = random.choice(respuestas_repetitivas)
            return {"respuesta": respuesta_variable}

        
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

