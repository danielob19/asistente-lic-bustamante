# 📦 Módulos estándar de Python
import os
import time
import threading
import random
import re
from datetime import datetime, timedelta
from collections import Counter
from typing import List, Optional

# 🧪 Librerías externas
import psycopg2
import openai
from pydantic import BaseModel

# 🚀 Framework FastAPI
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

# 🧠 Diccionario de sesiones por usuario (en memoria)
user_sessions = {}

# 🤖 Módulo del "cerebro simulado"
from cerebro_simulado import (
    predecir_evento_futuro,
    inferir_patron_interactivo,
    evaluar_coherencia_mensaje,
    clasificar_estado_mental,
    inferir_intencion_usuario
)

# 🧾 Respuestas clínicas fijas
from respuestas_clinicas import RESPUESTAS_CLINICAS

# 📩 Funciones auxiliares
from core.utils_contacto import es_consulta_contacto, obtener_mensaje_contacto
from core.utils_seguridad import contiene_elementos_peligrosos
from core.faq_semantica import generar_embeddings_faq, buscar_respuesta_semantica_con_score

# ⚙️ Constantes
from core.constantes import (
    CLINICO_CONTINUACION, SALUDO, CORTESIA,
    ADMINISTRATIVO, CLINICO, CONSULTA_AGENDAR,
    CONSULTA_MODALIDAD
)

# 📁 Funciones de base de datos reestructuradas
from core.db.registro import (
    registrar_emocion,
    registrar_interaccion,
    registrar_respuesta_openai,
    registrar_auditoria_input_original,
    registrar_similitud_semantica,
    registrar_log_similitud,
    registrar_auditoria_respuesta,
    registrar_inferencia,
)

from core.db.sintomas import (
    registrar_sintoma,
    actualizar_sintomas_sin_estado_emocional,
    obtener_sintomas_existentes,
    obtener_sintomas_con_estado_emocional,
    obtener_coincidencias_sintomas_y_registrar,
)

from core.db.consulta import (
    obtener_emociones_ya_registradas,
    obtener_combinaciones_no_registradas,
)


CLINICO_CONTINUACION = "CLINICO_CONTINUACION"
SALUDO = "SALUDO"
CORTESIA = "CORTESIA"
ADMINISTRATIVO = "ADMINISTRATIVO"
CLINICO = "CLINICO"
CONSULTA_AGENDAR = "CONSULTA_AGENDAR"
CONSULTA_MODALIDAD = "CONSULTA_MODALIDAD"


# Configuración de la clave de API de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("OPENAI_API_KEY no está configurada en las variables de entorno.")

# Configuración de la URL de la base de datos PostgreSQL
DATABASE_URL = "postgresql://my_postgres_db_oahe_user:AItPOENiOHIGPNva0eiCT0kK1od4UhZf@dpg-ctqqj0bqf0us73f4ar1g-a/my_postgres_db_oahe"

# Generación de respuestas con OpenAI
def generar_respuesta_con_openai(prompt, contador: int = 0, user_id: str = "", mensaje_usuario: str = "", mensaje_original: str = ""):
    try:
        print("\n===== DEPURACIÓN - GENERACIÓN DE RESPUESTA CON OPENAI =====")
        print(f"📤 Prompt enviado a OpenAI: {prompt}\n")

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.3
        )

        respuesta = response.choices[0].message['content'].strip()
        print(f"📥 Respuesta generada por OpenAI: {respuesta}\n")

        # ❌ Filtro para mención indebida a contacto antes de interacción 5, 9 o 10+
        if (
            "bustamante" in respuesta.lower()
            and contador not in [5, 9] and contador < 10
            and not es_consulta_contacto(mensaje_usuario, user_id, mensaje_original)
        ):
            respuesta_filtrada = re.sub(
                r"(con\s+)?(el\s+)?Lic(\.|enciado)?\s+Daniel\s+O\.?\s+Bustamante.*?(\.|\n|$)",
                "", respuesta, flags=re.IGNORECASE
            )
            print("🔒 Mención indebida al Lic. Bustamante detectada y eliminada.\n")
            return respuesta_filtrada.strip()

        return respuesta

    except Exception as e:
        print(f"❌ Error al generar respuesta con OpenAI: {e}")
        return "Lo siento, hubo un problema al generar una respuesta. Por favor, intenta nuevamente."

def estandarizar_emocion_detectada(emocion: str) -> str:
    emocion = emocion.strip().lower()
    emocion = re.sub(r"[.,;:!¡¿?]+$", "", emocion)
    return emocion

def es_tema_clinico_o_emocional(mensaje: str) -> bool:
    if not mensaje or not isinstance(mensaje, str):
        return False

    mensaje = mensaje.lower().strip()

    # Palabras clave clínicas frecuentes
    palabras_clave = [
        "triste", "ansioso", "angustia", "ansiedad", "vacío", "dolor", "sufrimiento",
        "miedo", "enojo", "culpa", "vergüenza", "desesperanza", "soledad", "estrés",
        "abandono", "apatía", "insomnio", "despersonalización", "fobia", "ataques de pánico",
        "indecisión súbita", "desborde", "desbordamiento", "nervioso", "desesperado",
        "indiferente", "ya no siento", "nada me entusiasma", "me quiero morir",
        "pienso en morirme", "no me reconozco", "todo me supera", "no puedo dormir"
    ]
    if any(palabra in mensaje for palabra in palabras_clave):
        return True

    # Patrones típicos de malestar emocional
    patrones_emocionales = [
        r"me cuesta\s+(vivir|seguir|levant[a-z]+|encontrarle sentido)",
        r"no\s+(puedo|quiero|logro)\b.*",
        r"ya no\s+(disfruto|me interesa|me importa)",
        r"siento que\s+(todo está mal|no valgo|todo es en vano)",
        r"me siento\s+(perdido|vacío|cansado|agotado|confundido|sin sentido)",
        r"no le encuentro sentido\s+(a la vida|a nada|a esto)",
        r"no tengo ganas", r"nada me importa", r"todo me cuesta", r"nada vale la pena",
        r"no sirvo para nada", r"siento que no sirvo", r"me cuesta\s+(vivir|seguir|todo)",
        r"no sé si esto es normal", r"me siento perdido", r"siento que no puedo más",
        r"me siento solo", r"todo me da igual", r"me tiene sin ganas",
        r"no duermo", r"no puedo dormir", r"no tengo energía",
    ]
    if any(re.search(p, mensaje) for p in patrones_emocionales):
        return True

    # ⚠️ Nuevos patrones de aislamiento o desinterés confundidos con cortesía
    patrones_aislamiento = [
        r"\bno\s+me\s+interesa\s+hablar\s+con\s+nadie\b",
        r"\bno\s+quiero\s+hablar\s+con\s+nadie\b",
        r"\bno\s+quiero\s+ver\s+a\s+nadie\b",
        r"\bno\s+tengo\s+ganas\s+de\s+hablar\b",
        r"\bprefiero\s+estar\s+solo[a]?\b",
        r"\bquiero\s+aislarme\b"
    ]
    if any(re.search(p, mensaje) for p in patrones_aislamiento):
        return True

    return False


# 📎 Respuesta profesional para mensajes fuera de contexto clínico o emocional
def respuesta_default_fuera_de_contexto():
    return (
        "Este espacio está destinado exclusivamente a consultas vinculadas al bienestar emocional y psicológico. "
        "Si lo que querés compartir tiene relación con alguna inquietud personal, emocional o clínica, "
        "estoy disponible para acompañarte desde ese lugar."
    )


# Función para detectar emociones negativas usando OpenAI
def detectar_emociones_negativas(mensaje):
    if not mensaje or not isinstance(mensaje, str):
        print("⚠️ Input inválido para detectar emociones: no es string o es None")
        return []

    prompt = (
        "Analizá el siguiente mensaje desde una perspectiva clínica y detectá exclusivamente emociones negativas o estados afectivos vinculados a malestar psicológico. "
        "Tu tarea es identificar manifestaciones emocionales que indiquen sufrimiento, alteración afectiva o malestar clínico.\n\n"

        "Indicaciones:\n"
        "- Devolvé una lista separada por comas, sin explicaciones ni texto adicional.\n"
        "- Si hay ambigüedad, asigná la emoción negativa más cercana desde el punto de vista clínico.\n"
        "- Si hay múltiples emociones, incluilas todas separadas por comas.\n"
        "- Si no se detectan emociones negativas, devolvé únicamente: ninguna.\n\n"

        "Ejemplos clínicamente válidos:\n"
        "- Emociones simples: tristeza, ansiedad, culpa, vergüenza, impotencia, miedo, irritabilidad, angustia.\n"
        "- Estados complejos: vacío emocional, desgaste emocional, desesperanza, sensación de abandono, temor al rechazo, apatía profunda.\n\n"
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

        print("\n===== DEPURACIÓN - DETECCIÓN DE EMOCIONES =====")
        print(f"Mensaje analizado: {mensaje}")
        print(f"Respuesta de OpenAI: {emociones}")

        emociones = emociones.replace("emociones negativas detectadas:", "").strip()
        emociones = [emocion.strip() for emocion in emociones.split(",") if emocion.strip()]

        if "ninguna" in emociones:
            print("No se detectaron emociones negativas.\n")
            return []

        print(f"Emociones detectadas: {emociones}\n")
        return emociones

    except Exception as e:
        print(f"❌ Error al detectar emociones negativas: {e}")
        return []


# Generar frase disparadora según emoción detectada
def generar_disparador_emocional(emocion):
    disparadores = {
        "tristeza": "La tristeza puede ser muy pesada. A veces aparece sin aviso y cuesta ponerla en palabras.",
        "ansiedad": "La ansiedad a veces no tiene una causa clara, pero se siente intensamente en el cuerpo y en los pensamientos.",
        "culpa": "La culpa suele cargar con cosas no dichas o no resueltas.",
        "enojo": "El enojo puede ser una forma de defensa frente a algo que dolió primero.",
        "miedo": "El miedo muchas veces se disfraza de prudencia o de silencio, pero su impacto se nota.",
        "confusión": "La confusión puede surgir cuando algo en nuestro mundo interno se mueve sin aviso.",
        "desgano": "A veces el desgano no es flojera, sino cansancio de sostener tanto por dentro.",
        "agotamiento": "El agotamiento emocional aparece cuando dimos mucho y recibimos poco o nada.",
        "soledad": "La soledad puede sentirse incluso rodeado de personas. A veces es una falta de resonancia más que de compañía."
    }
    return disparadores.get(emocion.lower())

# Gestionar combinación emocional devolviendo una frase o registrándola si es nueva
def gestionar_combinacion_emocional(emocion1, emocion2):
    """
    Consulta la tabla 'disparadores_emocionales' para una frase clínica correspondiente a una combinación de emociones.
    Si no la encuentra, registra automáticamente la combinación en 'combinaciones_no_registradas'.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        # Consulta para buscar el disparador emocional clínico, sin importar el orden
        consulta = """
            SELECT texto_disparador FROM disparadores_emocionales
            WHERE (emocion_1 = %s AND emocion_2 = %s)
               OR (emocion_1 = %s AND emocion_2 = %s)
            LIMIT 1;
        """
        cursor.execute(consulta, (emocion1, emocion2, emocion2, emocion1))
        resultado = cursor.fetchone()

        if resultado:
            conn.close()
            return resultado[0]

        # Registrar la combinación no contemplada
        print(f"🆕 Combinación emocional no registrada: {emocion1} + {emocion2}")
        cursor.execute("""
            INSERT INTO combinaciones_no_registradas (emocion_1, emocion_2)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING;
        """, (emocion1.lower(), emocion2.lower()))

        conn.commit()
        conn.close()
        return None

    except Exception as e:
        print(f"❌ Error al gestionar combinación emocional: {e}")
        return None

# Inicialización de FastAPI
app = FastAPI()

# 📌 Importar y montar el router de /asistente
from routes.asistente import router as asistente_router
app.include_router(asistente_router)

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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inferencias_cerebro_simulado (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                interaccion_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                valor TEXT NOT NULL,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()
        print("Base de datos inicializada en PostgreSQL.")
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")

# Lista de palabras irrelevantes
palabras_irrelevantes = {
    "un", "una", "el", "la", "lo", "es", "son", "estoy", "siento", "me siento", "tambien", "tambien tengo", "que", "de", "en", 
    "por", "a", "me", "mi", "tengo", "mucho", "muy", "un", "poco", "tengo", "animicos", "si", "supuesto", "frecuentes", "verdad", "sé", "hoy", "quiero", 
    "bastante", "mucho", "tambien", "gente", "frecuencia", "entendi", "hola", "estoy", "vos", "entiendo", 
    "soy", "mi", "de", "es", "4782-6465", "me", "siento", "para", "mucha", "y", "sufro", "vida", 
    "que", "opinas", "¿","?", "reinicia", "con", "del", "necesito", "me", "das"
}

def purificar_input_clinico(texto: str) -> str:
    import re

    try:
        if not isinstance(texto, str):
            return ""

        texto_original = texto.strip().lower()

        texto = texto_original

        # 🛡️ Detectar negación para no perder sentido clínico
        negadores_criticos = ["nada", "nadie", "ninguno", "ninguna", "no"]
        contiene_negador = any(re.search(rf'\b{n}\b', texto_original) for n in negadores_criticos)

        # 🗑️ Limpieza de muletillas
        muletillas = [
            r'\b(este|eh+|mmm+|ajá|tipo|digamos|sea|viste|bueno|a ver|me explico|ehh*)\b',
            r'\b(sí|si|claro)\b'
        ]
        for patron in muletillas:
            texto = re.sub(patron, '', texto, flags=re.IGNORECASE)

        texto = re.sub(r'\s{2,}', ' ', texto).strip()

        # ✅ Coincidencias clínicas completas
        coincidencias_exactas = {
            "nada me entusiasma, ni siquiera lo que solía gustarme": "anhedonia",
            "nada me importa, ni lo que antes me importaba": "apatía profunda",
            "no quiero ver a nadie ni salir de casa": "aislamiento",
            "pienso en morirme todo el tiempo": "ideación suicida",
            "lloro sin razón y no sé por qué": "llanto sin motivo"
        }
        for frase, valor in coincidencias_exactas.items():
            if frase in texto:
                texto = valor
                break

        # ✂️ Limpieza final y estandarización gramatical
        texto = re.sub(r'\b(\w{1}) (\w+)', r'\1 \2', texto)
        texto = re.sub(r'(\.{2,})', '.', texto)
        texto = re.sub(r'(,{2,})', ',', texto)
        texto = re.sub(r'[\s\.,!?]+$', '', texto)
        texto = texto.strip()

        # Capitalización
        if texto:
            texto = texto[0].upper() + texto[1:]

        return texto

    except Exception as e:
        print(f"[Error] purificar_input_clinico: {e}")
        return ""

# Análisis de texto del usuario
def analizar_texto(mensajes_usuario):
    """
    Analiza los mensajes del usuario para detectar coincidencias con los síntomas almacenados
    y muestra un cuadro probable y emociones o patrones de conducta adicionales detectados.
    """
    sintomas_existentes = obtener_sintomas_con_estado_emocional()
    if not sintomas_existentes:
        return "No se encontraron síntomas en la base de datos para analizar."

    keyword_to_cuadro = {sintoma.lower(): cuadro for sintoma, cuadro in sintomas_existentes}
    sintomas_registrados = {sintoma.lower() for sintoma, _ in sintomas_existentes}

    coincidencias = []
    emociones_detectadas = []
    nuevos_sintomas = []

    for mensaje in mensajes_usuario:
        user_words = mensaje.lower().split()
        user_words = [
            palabra for palabra in user_words
            if palabra not in palabras_irrelevantes and len(palabra) > 2 and palabra.isalpha()
        ]

        for palabra in user_words:
            if palabra in keyword_to_cuadro:
                coincidencias.append(keyword_to_cuadro[palabra])
            elif palabra not in nuevos_sintomas:
                nuevos_sintomas.append(palabra)

    # Registrar síntomas nuevos sin cuadro clínico
    for sintoma in nuevos_sintomas:
        if sintoma not in sintomas_registrados:
            registrar_sintoma(sintoma, None)

    # Generar emociones detectadas si hay pocas coincidencias
    if len(coincidencias) < 2:
        texto_usuario = " ".join(mensajes_usuario)
        prompt = (
            f"Detectá emociones negativas o patrones emocionales con implicancia clínica en el siguiente texto del usuario:\n\n"
            f"{texto_usuario}\n\n"
            "Identificá únicamente términos emocionalmente relevantes (individuales o compuestos), separados por comas, sin explicaciones adicionales.\n\n"
            "Si el contenido no incluye ningún elemento clínico relevante, respondé únicamente con 'ninguna'."
        )

        try:
            emociones_detectadas = generar_respuesta_con_openai(prompt).split(",")
            emociones_detectadas = [
                emocion.strip().lower() for emocion in emociones_detectadas
                if emocion.strip().lower() not in palabras_irrelevantes
            ]

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
            f"el malestar emocional predominante es: {cuadro_probable}. "
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

# 🧠 Cache de síntomas registrados en la base
sintomas_cacheados = set()

@app.on_event("startup")
def startup_event():
    init_db()                          # 🧱 Inicializa la base de datos
    generar_embeddings_faq()          # 🧠 Genera embeddings de FAQ al iniciar
    start_session_cleaner()           # 🧹 Limpia sesiones inactivas

    # 🚀 Inicializar cache de síntomas registrados
    global sintomas_cacheados
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT LOWER(sintoma) FROM palabras_clave")
        sintomas = cursor.fetchall()
        sintomas_cacheados = {s[0].strip() for s in sintomas if s[0]}
        conn.close()
        print(f"✅ Cache inicial de síntomas cargado: {len(sintomas_cacheados)} ítems.")
    except Exception as e:
        print(f"❌ Error al inicializar cache de síntomas: {e}")


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

# 🧾 Función para generar resumen clínico y estado predominante
def generar_resumen_clinico_y_estado(session: dict, contador: int) -> str:
    """
    Genera una respuesta clínica con base en emociones detectadas y síntomas coincidentes.
    Se aplica en la interacción 5 y 9, devolviendo síntomas literales y estado emocional predominante.
    """

    mensajes = session.get("mensajes", [])
    emociones_acumuladas = session.get("emociones_detectadas", [])

    # ✅ Detectar nuevas emociones (previniendo errores por string vacío)
    texto_emocional = " - ".join(mensajes).strip()
    emociones_detectadas = detectar_emociones_negativas(texto_emocional) if texto_emocional else []

    # 🧩 Unificación sin duplicados
    emociones_unificadas = list(set(emociones_acumuladas + emociones_detectadas))
    session["emociones_detectadas"] = emociones_unificadas

    if not emociones_unificadas:
        print(f"⚠️ No se detectaron emociones al llegar a la interacción {contador}")
        return (
            "No se identificaron emociones predominantes en este momento. "
            "Te sugiero contactar al Lic. Bustamante al WhatsApp +54 911 3310-1186 para una evaluación más precisa."
        )

    coincidencias_sintomas = obtener_coincidencias_sintomas_y_registrar(emociones_unificadas)
    cuadro_predominante = (
        Counter(coincidencias_sintomas).most_common(1)[0][0]
        if len(coincidencias_sintomas) >= 2
        else "No se pudo establecer con certeza un estado emocional predominante."
    )

    emociones_literal = " - ".join(emociones_unificadas[:3])

    respuesta = (
        f"Con base a lo que has descripto —{emociones_literal}—, "
        f"pareciera ser que el malestar emocional predominante es: {cuadro_predominante}."
    )

    # ✅ Sugerencia de contacto solo en interacciones 5, 9 y 10
    if contador in [5, 9, 10]:
        respuesta += (
            " ¿Te interesaría consultarlo con el Lic. Daniel O. Bustamante? "
            "Podés escribirle al WhatsApp +54 911 3310-1186 para una evaluación más detallada."
        )

    print(f"📋 Resumen clínico generado correctamente en interacción {contador}")
    session["mensajes"].clear()
    return respuesta

def inferir_emocion_no_dicha(emociones_detectadas: List[str], conexion_pgsql) -> Optional[str]:
    """
    Simula una inferencia clínica basada en combinaciones frecuentes.
    Sugiere una emoción no mencionada aún por el usuario, usando la base de datos como memoria clínica.
    """
    if not emociones_detectadas:
        return None

    try:
        with conexion_pgsql.cursor() as cursor:
            cursor.execute("""
                SELECT estado_emocional, COUNT(*) as frecuencia
                FROM palabras_clave
                WHERE sintoma = ANY(%s)
                GROUP BY estado_emocional
                ORDER BY frecuencia DESC
                LIMIT 1
            """, (emociones_detectadas,))
            resultado = cursor.fetchone()
            if resultado and resultado[0].lower().strip() not in emociones_detectadas:
                return resultado[0]
    except Exception as e:
        print("❌ Error en inferencia emocional:", e)

    return None
    
def hay_contexto_clinico_anterior(user_id: str) -> bool:
    """
    Evalúa si ya hay emociones detectadas en la sesión del usuario.
    Se considera que hay contexto clínico previo si hay al menos una emoción registrada.
    """
    session = user_sessions.get(user_id)
    if session and session.get("emociones_detectadas"):
        return len(session["emociones_detectadas"]) >= 1
    return False


def generar_resumen_interaccion_9(session, user_id, interaccion_id, contador):
    print("🧩 Generando resumen clínico en interacción 9")

    mensajes_6_a_9 = session["mensajes"][-4:]
    emociones_nuevas = []

    for mensaje in mensajes_6_a_9:
        if mensaje.strip():
            nuevas = detectar_emociones_negativas(mensaje) or []
            for emocion in nuevas:
                emocion = emocion.lower().strip()
                emocion = re.sub(r'[^\w\sáéíóúüñ]+$', '', emocion)
                if emocion not in session["emociones_detectadas"]:
                    emociones_nuevas.append(emocion)

    if emociones_nuevas:
        session["emociones_detectadas"].extend(emociones_nuevas)
        emociones_registradas_bd = obtener_emociones_ya_registradas(user_id, contador)
        for emocion in emociones_nuevas:
            if emocion not in emociones_registradas_bd:
                registrar_emocion(emocion, f"interacción {contador}", user_id)

    estado_global = clasificar_estado_mental(session["mensajes"])
    if estado_global != "estado emocional no definido":
        print(f"📊 Estado global sintetizado: {estado_global}")
        registrar_inferencia(user_id, contador, "estado_mental", estado_global)

    try:
        conn = psycopg2.connect(DATABASE_URL)
        emocion_inferida = inferir_emocion_no_dicha(session["emociones_detectadas"], conn)
        conn.close()
    except Exception as e:
        print(f"⚠️ Error en inferencia conexión BD: {e}")
        emocion_inferida = None

    if emocion_inferida and emocion_inferida not in session["emociones_detectadas"]:
        session["emociones_detectadas"].append(emocion_inferida)
        registrar_emocion(emocion_inferida, f"confirmación de inferencia (interacción {contador})", user_id)
        session["emocion_inferida_9"] = emocion_inferida

    emociones_literal = ", ".join(session["emociones_detectadas"])
    respuesta = (
        f"Por lo que comentás, pues al malestar anímico que describiste anteriormente, "
        f"advierto que se suman {emociones_literal}, por lo que daría la impresión de que se trata "
        f"de un estado emocional predominantemente {estado_global}. "
    )

    if emocion_inferida:
        respuesta += (
            f"Además, ¿dirías que también podrías estar atravesando cierta {emocion_inferida}? "
            f"Lo pregunto porque suele aparecer en casos similares. "
        )

    respuesta += (
        "No obstante, para estar seguros se requiere de una evaluación psicológica profesional. "
        "Te sugiero que te contactes con el Lic. Bustamante. "
        "Lamentablemente, no puedo continuar con la conversación más allá de este punto."
    )

    session["resumen_generado"] = True
    registrar_respuesta_openai(interaccion_id, respuesta)
    return respuesta


def generar_resumen_interaccion_5(session, user_id, interaccion_id, contador):
    print("🧩 Generando resumen clínico en interacción 5")

    emociones_previas = session.get("emociones_detectadas", [])
    mensajes_previos = session.get("mensajes", [])
    nuevas_emociones = []

    for mensaje in mensajes_previos:
        if mensaje.strip():
            nuevas = detectar_emociones_negativas(mensaje) or []
            for emocion in nuevas:
                emocion = emocion.lower().strip()
                emocion = re.sub(r'[^\w\sáéíóúüñ]+$', '', emocion)
                if emocion not in emociones_previas:
                    nuevas_emociones.append(emocion)

    if nuevas_emociones:
        session["emociones_detectadas"].extend(nuevas_emociones)
        emociones_registradas_bd = obtener_emociones_ya_registradas(user_id, contador)
        for emocion in nuevas_emociones:
            if emocion not in emociones_registradas_bd:
                registrar_emocion(emocion, f"interacción {contador}", user_id)

    estado_global = clasificar_estado_mental(mensajes_previos)
    if estado_global != "estado emocional no definido":
        print(f"📊 Estado global sintetizado: {estado_global}")
        registrar_inferencia(user_id, contador, "estado_mental", estado_global)

    try:
        conn = psycopg2.connect(DATABASE_URL)
        emocion_inferida = inferir_emocion_no_dicha(session["emociones_detectadas"], conn)
        conn.close()
    except Exception as e:
        print(f"⚠️ Error al conectar a la base para inferencia en interacción 5: {e}")
        emocion_inferida = None

    if emocion_inferida and emocion_inferida not in session["emociones_detectadas"]:
        session["emocion_inferida_5"] = emocion_inferida

    if session["emociones_detectadas"]:
        emociones_literal = ", ".join(session["emociones_detectadas"])
        resumen = (
            f"Por lo que mencionaste hasta ahora, se identifican las siguientes emociones: {emociones_literal}. "
            f"Impresiona ser un estado emocional predominantemente {estado_global}. "
        )
    else:
        resumen = (
            f"Por lo que mencionaste hasta ahora, se observa un malestar anímico que daría la impresión de corresponder "
            f"a un estado emocional predominantemente {estado_global}. "
        )

    if emocion_inferida:
        resumen += (
            f"Además, ¿dirías que también podrías estar atravesando cierta {emocion_inferida}? "
            f"Lo pregunto porque suele aparecer en casos similares."
        )
    else:
        resumen += "¿Te interesaría consultarlo con el Lic. Daniel O. Bustamante?"

    session["resumen_generado"] = True
    registrar_respuesta_openai(interaccion_id, resumen)
    return resumen


def generar_resumen_interaccion_10(session, user_id, interaccion_id, contador):
    print("🔒 Cierre definitivo activado en la interacción 10")

    emocion_inferida = session.get("emocion_inferida_9")
    mensaje_usuario_actual = session["mensajes"][-1] if session["mensajes"] else ""

    # Confirmación de inferencia si el usuario lo acepta explícitamente
    if emocion_inferida and (
        emocion_inferida in mensaje_usuario_actual
        or "sí" in mensaje_usuario_actual
        or "me pasa" in mensaje_usuario_actual
    ):
        if emocion_inferida not in session["emociones_detectadas"]:
            session["emociones_detectadas"].append(emocion_inferida)
            registrar_emocion(emocion_inferida, "confirmación de inferencia (interacción 10)", user_id)

    # Guardar resumen clínico total
    resumen_total = generar_resumen_clinico_y_estado(session, contador)
    session["resumen_clinico_total"] = resumen_total

    # Redacción del mensaje de cierre definitivo
    respuesta = (
        "He encontrado interesante nuestra conversación, pero para profundizar más en el análisis de tu malestar, "
        "sería ideal que consultes con un profesional. Por ello, te sugiero que te contactes con el Lic. Bustamante. "
        "Lamentablemente, no puedo continuar con la conversación más allá de este punto."
    )

    # Agregar predicción de desenlace si fue inferida
    prediccion = predecir_evento_futuro(session["mensajes"])
    if prediccion != "sin predicción identificada":
        print(f"🔮 Proyección detectada: {prediccion}")
        registrar_inferencia(user_id, contador, "prediccion", prediccion)
        respuesta += f" Por otra parte, se identificó que mencionaste una posible consecuencia o desenlace: {prediccion}."

    # Registrar y retornar
    registrar_respuesta_openai(interaccion_id, respuesta)
    return respuesta


@app.post("/asistente")
async def asistente(input_data: UserInput):
    try:
        user_id = input_data.user_id
        mensaje_original = input_data.mensaje

        if not mensaje_original or not isinstance(mensaje_original, str):
            raise HTTPException(status_code=400, detail="El mensaje recibido no es válido.")
        
        mensaje_original = mensaje_original.strip()
        mensaje_usuario = mensaje_original.lower()


        # ✅ Frases neutrales que no deben analizarse emocionalmente
        EXPRESIONES_DESCARTADAS = [
            # Cortesía, cierre o testeo
            "gracias", "ok", "listo", "ya está", "nada más", "solo eso", "solo quería saber eso",
            "me quedó claro", "ya entendí", "era solo una duda", "era curiosidad", "me lo guardo",
            "te consultaba por otra persona", "me interesaba saber", "después veo", "lo consulto luego",
            "más adelante veo", "ah ok", "claro", "entiendo", "lo veo después", "todo bien", "sí",
        
            # Preguntas neutras o generales
            "¿a quién me recomiendas?", "a quién me recomiendas", "me recomendarías a alguien?",
            "qué opinas?", "el atiende estos casos?", "que tipo de casos atienden?"
        ]

        # Comentarios metaconversacionales o de expectativa que no deben generar análisis clínico
        EXPRESIONES_ESPERADAS_NO_CLINICAS = [
            "esto funciona como terapia", "me gustaría que esto funcione como terapia",
            "es como una consulta", "esto parece una consulta", "esto me ayuda como si fuera terapia",
            "siento que esto es una sesión", "esto me resulta terapéutico", "parece una sesión real"
        ]
        
        if any(expresion in mensaje_usuario for expresion in EXPRESIONES_ESPERADAS_NO_CLINICAS):
            registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, "EXPECTATIVA_NO_CLINICA")
            return {
                "respuesta": (
                    "Este espacio está diseñado para brindar orientación clínica general. "
                    "Si hay algo puntual que te gustaría compartir sobre tu estado emocional, podés hacerlo con confianza."
                )
            }
        

        if not mensaje_usuario:
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

        # 🧩 Clasificación local por intención general
        tipo_input = clasificar_input_inicial(mensaje_usuario)

        # 🧠 Inferencia cognitiva adicional sobre intención del usuario
        intencion_inferida = inferir_intencion_usuario(mensaje_usuario)
        print(f"🧠 Intención inferida por el cerebro simulado: {intencion_inferida}")

        
        # ✅ Forzar continuidad clínica si el input es ambiguo pero hubo malestar antes
        if tipo_input in ["INDEFINIDO", "FUERA_DE_CONTEXTO", "CONFUSO"]:
            if hay_contexto_clinico_anterior(user_id):
                tipo_input = CLINICO_CONTINUACION
        
        # 🧠 Registrar todas las etiquetas anteriores en la sesión
        session = user_sessions.get(user_id, {
            "contador_interacciones": 0,
            "ultima_interaccion": time.time(),
            "mensajes": [],
            "emociones_detectadas": [],
            "ultimas_respuestas": [],
            "input_sospechoso": False,
            "interacciones_previas": []
        })
        session.setdefault("interacciones_previas", []).append(tipo_input)
        user_sessions[user_id] = session
        
                
        if tipo_input == SALUDO:
            registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, SALUDO)
            return {"respuesta": "¡Hola! ¿En qué puedo ayudarte hoy?"}
        
        elif tipo_input == CORTESIA:
            registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, CORTESIA)
            return {
                "respuesta": "Con gusto. Si necesitás algo más, estoy disponible para ayudarte."
            }
        
        elif tipo_input == ADMINISTRATIVO:
            registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, ADMINISTRATIVO)
            return {
                "respuesta": (
                    "¡Hola! Soy el asistente del Lic. Daniel O. Bustamante. "
                    + obtener_mensaje_contacto() +
                    "¿Hay algo más que te gustaría saber?"
                )
            }
        
        elif tipo_input == CLINICO_CONTINUACION:
            registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, CLINICO_CONTINUACION)
            return {
                "respuesta": (
                    "Entiendo. Lo que mencionaste antes podría estar indicando un malestar emocional. "
                    "¿Querés que exploremos un poco más lo que estás sintiendo últimamente?"
                )
            }
        

        # 🧠 Clasificación contextual con OpenAI
        try:
            prompt_contextual = (
                f"Analizá el siguiente mensaje del usuario y clasificá su intención principal, utilizando una única etiqueta válida.\n\n"
                f"Mensaje: '{mensaje_usuario}'\n\n"
                "Posibles etiquetas (escribilas exactamente como están):\n"
                "- CLINICO: si expresa malestar emocional, síntomas, angustia, ideas existenciales, desmotivación, llanto, insomnio, vacío, o cualquier signo de sufrimiento subjetivo.\n"
                "- CORTESIA: si solo agradece, cierra la conversación o expresa buenos modales sin intención emocional o clínica.\n"
                "- CONSULTA_AGENDAR: si consulta sobre turnos, disponibilidad, cómo coordinar una sesión, cómo pedir cita, cómo sacar turno, cuánto cuesta, etc.\n"
                "- CONSULTA_MODALIDAD: si consulta por la modalidad de atención (online/presencial), si es por videollamada, Zoom, ubicación o si debe asistir a un consultorio.\n"
                "- TESTEO: si es un mensaje de prueba sin contenido emocional ni administrativo (ejemplo: 'hola test', 'probando', '1,2,3', etc.).\n"
                "- MALICIOSO: si contiene lenguaje técnico, comandos, código de programación, frases extrañas, manipulación evidente o contenido ajeno a una conversación clínica.\n"
                "- IRRELEVANTE: si no tiene relación con la clínica psicológica ni con la consulta de servicios (ej: temas técnicos, bromas, frases absurdas, etc.).\n\n"
                "Respondé con una sola palabra en mayúsculas, sin explicaciones adicionales. Solamente devolvé la etiqueta elegida."
            )
     
            response_contextual = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt_contextual}],
                max_tokens=20,
                temperature=0.0
            )
        
            clasificacion = response_contextual.choices[0].message['content'].strip().upper()

            # 🔍 Validación robusta
            opciones_validas = {
                "CLINICO", "CORTESIA", "CONSULTA_AGENDAR", "CONSULTA_MODALIDAD",
                "TESTEO", "MALICIOSO", "IRRELEVANTE"
            }
            if clasificacion not in opciones_validas:
                print(f"⚠️ Clasificación inválida recibida de OpenAI: '{clasificacion}'")
                clasificacion = "IRRELEVANTE"
            
            if clasificacion == "CORTESIA":
                registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, CORTESIA)
                return {"respuesta": "Con gusto. Si necesitás algo más, estoy disponible para ayudarte."}
            
            if clasificacion == "CONSULTA_AGENDAR":
                registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, CONSULTA_AGENDAR)
                return {
                    "respuesta": (
                        "Para agendar una sesión o conocer disponibilidad, podés escribirle directamente al Lic. Bustamante al WhatsApp +54 911 3310-1186."
                    )
                }
            
            if clasificacion == "CONSULTA_MODALIDAD":
                registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, CONSULTA_MODALIDAD)
                return {
                    "respuesta": (
                        "El Lic. Bustamante atiende exclusivamente en modalidad Online, a través de videollamadas. "
                        "Podés consultarle directamente al WhatsApp +54 911 3310-1186 si querés coordinar una sesión."
                    )
                }
            
            if clasificacion in ["TESTEO", "MALICIOSO", "IRRELEVANTE"]:
                registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, clasificacion)
            
                # ⚠️ Solo bloquear si no hay contexto clínico previo
                if not hay_contexto_clinico_anterior(user_id):
                    session["input_sospechoso"] = True
                    return {"respuesta": respuesta_default_fuera_de_contexto()}
                else:
                    # ⚠️ Forzar que siga el flujo clínico como continuación
                    tipo_input = CLINICO_CONTINUACION
            
        
        except Exception as e:
            print(f"🧠❌ Error en clasificación contextual: {e}")
        
        # 🛡️ Etapa de blindaje contra inputs maliciosos
        def es_input_malicioso(texto: str) -> bool:
            patrones_maliciosos = [
                r"(\bimport\b|\bos\b|\bsystem\b|\beval\b|\bexec\b|\bopenai\.api_key\b)",  # Código Python
                r"(\bdrop\b|\bdelete\b|\binsert\b|\bupdate\b).*?\b(table|database)\b",     # SQL Injection
                r"(--|#|;|//).*?(drop|delete|system|rm\s+-rf)",                             # Comentarios maliciosos
                r"<script.*?>|</script>",                                                  # HTML/JS malicioso
                r"\b(shutdown|reboot|rm\s+-rf|mkfs|chmod|chown)\b"                          # Shell commands peligrosos
            ]
            for patron in patrones_maliciosos:
                if re.search(patron, texto, re.IGNORECASE):
                    return True
            return False
        
        if es_input_malicioso(mensaje_usuario):
            print("⚠️🔒 Input malicioso detectado y bloqueado:")
            print(f"   🔹 Usuario ID: {user_id}")
            print(f"   🔹 Mensaje purificado: {mensaje_usuario}")
            print(f"   🔹 Mensaje original: {mensaje_original}")
            
            registrar_auditoria_input_original(
                user_id,
                mensaje_original,
                mensaje_usuario + " [⚠️ DETECTADO COMO INPUT MALICIOSO]",
                "MALICIOSO"
            )
            
            return {
                "respuesta": (
                    "El sistema ha detectado que tu mensaje contiene elementos técnicos no compatibles con una consulta clínica. "
                    "Si tenés una duda o problema de salud emocional, podés contarme con confianza."
                )
            }

        # Registrar interacción con mensaje original incluido
        interaccion_id = registrar_interaccion(user_id, mensaje_usuario, mensaje_original)

        # 🔄 Si el input actual es ambiguo, pero ya hubo emociones antes, forzar continuidad clínica
        if tipo_input in ["FUERA_DE_CONTEXTO", "INDEFINIDO", "CONFUSO", "OTRO"]:
            if hay_contexto_clinico_anterior(user_id):
                tipo_input = CLINICO_CONTINUACION

        # Actualiza la sesión del usuario
        session["ultima_interaccion"] = time.time()
        session["contador_interacciones"] += 1  # ✅ Incrementar contador aquí
        contador = session["contador_interacciones"]
        session["mensajes"].append(mensaje_usuario)

# ====================== INTERACCIÓN 10 O POSTERIOR: CIERRE DEFINITIVO ======================

        # ✅ Activar cierre definitivo a partir de la interacción 10
        if contador >= 10:
            print(f"🔒 Interacción {contador}: se activó el modo de cierre definitivo. No se realizará nuevo análisis clínico.")
        
            # 🧠 Detección de intención de cierre con cerebro_simulado
            cierre_detectado = inferir_intencion_usuario(session["mensajes"])
            print(f"🧠 Intención inferida por el cerebro simulado: {cierre_detectado}")
        
            if cierre_detectado == "intencion de cierre":
                registrar_inferencia(user_id, contador, "intencion_de_cierre", cierre_detectado)
                respuesta = (
                    "Gracias por tu mensaje. Me alegra haber podido brindarte orientación en este espacio. "
                    "Si en algún momento deseás avanzar con una consulta, podés escribirle al Lic. Bustamante. "
                    + obtener_mensaje_contacto()
                )
            else:
                cantidad_emociones = len(set(session.get("emociones_detectadas", [])))
                if cantidad_emociones >= 2:
                    respuestas_cierre = [
                        "Gracias por compartir lo que estás sintiendo. Ya hemos recorrido juntos un análisis significativo. Para seguir avanzando, te recomiendo contactar al Lic. Bustamante. " + obtener_mensaje_contacto(),
                        "Valoro la confianza con la que expresaste tus emociones. Este espacio ya cumplió su función de orientación. Para una atención personalizada, podés continuar con el Lic. Bustamante. " + obtener_mensaje_contacto(),
                        "Hemos llegado al punto en que una intervención profesional directa sería lo más adecuado. El Lic. Bustamante está disponible para ayudarte. " + obtener_mensaje_contacto(),
                        "Agradezco tu apertura durante esta conversación. Para seguir explorando lo que estás atravesando en profundidad, lo ideal es hacerlo con el Lic. Bustamante en un entorno clínico. " + obtener_mensaje_contacto(),
                        "Lo que compartiste ha sido importante. A partir de aquí, solo un espacio terapéutico puede brindarte el acompañamiento que necesitás. " + obtener_mensaje_contacto()
                    ]
                else:
                    respuestas_cierre = [
                        "Este espacio ha llegado a su límite. Si deseás avanzar con una consulta, podés escribirle al Lic. Bustamante. " + obtener_mensaje_contacto(),
                        "Para continuar, es necesario un espacio clínico adecuado. Podés contactar al Lic. Bustamante si querés seguir con esta consulta. " + obtener_mensaje_contacto(),
                        "Este asistente ha cumplido su función orientativa. Para una atención más profunda, podés escribirle al Lic. Bustamante. " + obtener_mensaje_contacto()
                    ]
        
                respuesta = random.choice(respuestas_cierre)
        
            registrar_respuesta_openai(interaccion_id, respuesta)
            return {"respuesta": respuesta}

        # ✅ Si hay una respuesta clínica manual para esta interacción, se devuelve directamente
        # 🔄 (Se reemplazó el uso de 'respuestas_personalizadas' por 'RESPUESTAS_CLINICAS' del módulo importado)
        if contador in RESPUESTAS_CLINICAS:
            respuesta_manual = RESPUESTAS_CLINICAS[contador]
        
            # Auditoría (registro explícito como respuesta manual no generada por OpenAI)
            registrar_auditoria_respuesta(
                user_id=user_id,
                respuesta_original=respuesta_manual,
                respuesta_final=respuesta_manual,
                motivo_modificacion="respuesta manual predefinida"
            )
        
            return {"respuesta": respuesta_manual}
                   
        if contador == 10:
            respuesta = generar_resumen_interaccion_10(session, user_id, interaccion_id, contador)
            return {"respuesta": respuesta}

        # ✅ Confirmación de inferencia emocional previa entre interacciones 6 a 8
        if 6 <= contador <= 8 and session.get("emocion_inferida_5"):
            emocion = session["emocion_inferida_5"]
            if emocion in mensaje_usuario or "sí" in mensaje_usuario or "me pasa" in mensaje_usuario:
                if emocion not in session["emociones_detectadas"]:
                    session["emociones_detectadas"].append(emocion)
                    registrar_emocion(emocion, f"confirmación de inferencia (interacción {contador})", user_id)
        
                return {
                    "respuesta": (
                        f"Gracias por confirmarlo. ¿Querés contarme un poco más sobre cómo se manifiesta esa {emocion}?"
                    )
                }

        # 🧠 Nueva respuesta para la PRIMERA INTERACCIÓN
        if contador == 1:
            # ⚠️ Reforzar que si es SALUDO + contenido clínico, se trate como clínico
            if tipo_input == SALUDO and es_tema_clinico_o_emocional(mensaje_usuario):
                tipo_input = CLINICO
        
            # ✅ Si es clínico o hay contexto clínico previo, generar respuesta profesional
            if tipo_input in [CLINICO, CLINICO_CONTINUACION] or hay_contexto_clinico_anterior(user_id) or es_tema_clinico_o_emocional(mensaje_usuario):
                saludo_inicio = "- Comenzá la respuesta con un saludo breve como “Hola, ¿qué tal?”.\n" if contador == 1 else ""
        
                prompt = (
                    f"Mensaje recibido del usuario: '{mensaje_usuario}'.\n\n"
                    "Redactá una respuesta breve, profesional y clínica como si fueras el asistente virtual del Lic. Daniel O. Bustamante, psicólogo.\n\n"
                    "Estilo y directrices obligatorias:\n"
                    "- Mantené un tono clínico, sobrio, profesional y respetuoso.\n"
                    f"{saludo_inicio}"
                    "- Si se detecta malestar emocional, formulá una observación objetiva con expresiones como: 'pareciera tratarse de...', 'podría vincularse a...', 'refiere a...' o 'se observa...'.\n"
                    "- Evitá cualquier frase emocional simulada (ej: 'te entiendo', 'estás en buenas manos', 'no estás solo/a', 'tranquilo/a', etc.).\n"
                    "- No uses frases motivacionales ni lenguaje coloquial (evitá: 'todo va a estar bien', 'contá conmigo', etc.).\n"
                    "- No uses lenguaje institucional como 'nuestro equipo', 'desde nuestro espacio', 'trabajamos en conjunto', etc.\n"
                    "- No brindes datos de contacto, precios, horarios, enlaces ni información administrativa.\n"
                    "- No recomiendes consultar con el Lic. Bustamante ni uses expresiones como 'consultar con un profesional', 'buscar ayuda especializada' u otras sugerencias implícitas.\n"
                    "- No formules preguntas como “¿Deseás que te facilite información sobre agendar?” ni menciones WhatsApp.\n"
                    "- No uses 'Estimado/a', ni encabezados de carta o email.\n"
                    "- Solamente si el mensaje es claramente clínico, generá una respuesta analítica breve y profesional.\n"
                    "- Si el mensaje no tiene contenido emocional o clínico relevante, devolvé una frase neutra como: 'Gracias por tu mensaje. ¿Hay algo puntual que te gustaría compartir o consultar en este espacio?'\n\n"
                    "IMPORTANTE:\n"
                    "- En las interacciones 1 a 4, nunca sugieras contacto ni derivación, salvo que el usuario lo pida explícitamente.\n"
                    "- Solo en las interacciones 5, 9 o a partir de la 10, podés aceptar que se mencione el contacto si fue solicitado.\n"
                )

       
                # ✅ Bloque de generación de respuesta clínica personalizada
                # Generación del prompt clínico personalizado según interacción
                prompt = (
                    f"Mensaje recibido del usuario: '{mensaje_usuario}'.\n"
                    "Redactá una respuesta breve, profesional y clínica como si fueras el asistente virtual del Lic. Daniel O. Bustamante, psicólogo.\n"
                    "Estilo y directrices obligatorias:\n"
                    "- Mantené un tono clínico, sobrio, profesional y respetuoso.\n"
                    "- Comenzá la respuesta con un saludo breve como 'Hola, ¿qué tal?' solo si es la interacción 1.\n"
                    "- Si se detecta malestar emocional, formulá una observación objetiva con expresiones como: 'se observa...', 'se advierte...', 'impresiona...', 'podría tratarse de...', 'da la sensación de ser...', 'normalmente se trata de un...', etc.\n"
                    "- Evitá la frase 'Pareciera tratarse de...' en todas las interacciones, excepto en la 5 y 9.\n"
                    "- En la interacción 1 usá la frase 'Se observa una vivencia de falta de sentido...'\n"
                    "- No uses agradecimientos en ninguna interacción (ni al inicio ni al final).\n"
                    "- No uses frases motivacionales ni simulaciones empáticas (ej: 'te entiendo', 'estás en buenas manos', etc.).\n"
                    "- No uses lenguaje institucional ni expresiones como 'nuestro equipo', 'desde este espacio', etc.\n"
                    "- No brindes datos de contacto, precios ni derivaciones, salvo que sea interacción 5, 9 o a partir de la 10.\n"
                    "- Solo si el mensaje es claramente clínico, generá una respuesta analítica breve y profesional.\n"
                    "- Si no tiene contenido clínico o emocional, devolvé una frase neutra: 'Gracias por tu mensaje. ¿Hay algo puntual que te gustaría compartir o consultar en este espacio?'\n"
                    f"- IMPORTANTE: estás en la interacción {contador}.\n"
                )
                
                # Solicitar respuesta a OpenAI con el nuevo prompt clínico
                respuesta_original = generar_respuesta_con_openai(prompt, contador, user_id, mensaje_usuario, mensaje_original)
                
                # 🔍 Filtro para remover saludo 'Hola, ¿qué tal?' si no es la primera interacción
                if contador != 1 and respuesta_original.strip().lower().startswith("hola, ¿qué tal?"):
                    respuesta_filtrada = respuesta_original.replace("Hola, ¿qué tal? ", "", 1).strip()
                    motivo = "Se eliminó el saludo inicial 'Hola, ¿qué tal?' porque no corresponde repetirlo en interacciones posteriores a la primera"
                    registrar_auditoria_respuesta(user_id, respuesta_original, respuesta_filtrada, motivo)
                    respuesta_ai = respuesta_filtrada
                else:
                    respuesta_ai = respuesta_original
                

                # Filtrado de seguridad y registro de auditoría
                registrar_auditoria_respuesta(user_id, respuesta_original, respuesta_original)
                registrar_respuesta_openai(interaccion_id, respuesta_original)
        
                return {"respuesta": respuesta_original}
        
            # 🔹 Si no es clínico ni hay contexto previo, mantener respuesta neutra
            return {
                "respuesta": (
                    "Gracias por tu mensaje. ¿Hay algo puntual que te gustaría compartir o consultar en este espacio?"
                )
            }


        # 🟢 Si la frase es neutral, de cortesía o curiosidad, no analizar emocionalmente ni derivar
        if mensaje_usuario in EXPRESIONES_DESCARTADAS or any(p in mensaje_usuario for p in ["recomienda", "opinás", "atiende"]):
            return {
                "respuesta": (
                    "Gracias por tu mensaje. Si en algún momento deseás explorar una inquietud emocional, "
                    "estoy disponible para ayudarte desde este espacio."
                )
            }

                        
        # 🔍 Buscar coincidencia semántica en preguntas frecuentes
        resultado_semantico = buscar_respuesta_semantica_con_score(mensaje_usuario)
        if resultado_semantico:
            pregunta_faq, respuesta_semantica, similitud = resultado_semantico
        
            # Registrar respuesta en la interacción ya creada
            registrar_respuesta_openai(interaccion_id, respuesta_semantica)
        
            # Registrar similitud en la tabla correspondiente
            registrar_log_similitud(user_id, mensaje_usuario, pregunta_faq, similitud)
        
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
            if session["contador_interacciones"] >= 9 or session["mensajes"]:
                respuesta_clinica = generar_resumen_clinico_y_estado(session, contador)
                return {
                    "respuesta": (
                        f"{respuesta_clinica} En caso de que lo desees, podés contactar al Lic. Daniel O. Bustamante escribiéndole al WhatsApp +54 911 3310-1186."
                    )
                }
            return {"respuesta": "Entendido, quedo a tu disposición. Si necesitas algo más, no dudes en decírmelo."}

        
        if es_consulta_contacto(mensaje_usuario, user_id, mensaje_original):
            return {
                "respuesta": "Para contactar al Lic. Daniel O. Bustamante, podés enviarle un mensaje al WhatsApp +54 911 3310-1186. Él estará encantado de responderte."
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
           
        # Obtener la lista de síntomas ya registrados en la BD
        sintomas_existentes = obtener_sintomas_existentes()
        
        # Detectar emociones desde el mensaje actual
        emociones_detectadas = detectar_emociones_negativas(mensaje_usuario) or []
        
        # Filtrar emociones detectadas para evitar registrar duplicados
        emociones_nuevas = []
        
        for emocion in emociones_detectadas:
            emocion = emocion.lower().strip()

            # 🧼 Estandarizar emoción detectada (eliminar puntuación final innecesaria)
            emocion = re.sub(r'[^\w\sáéíóúüñ]+$', '', emocion)
        
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
                f"A partir de la siguiente emoción detectada: '{emocion}', asigná un único cuadro clínico o patrón emocional.\n\n"
                "Tu tarea es analizar el síntoma y determinar el estado clínico más adecuado, basándote en criterios diagnósticos de la psicología o la psiquiatría. "
                "No respondas con explicaciones, sólo con el nombre del cuadro clínico más pertinente.\n\n"
                "Si la emoción no corresponde a ningún cuadro clínico definido, indicá únicamente: 'Patrón emocional detectado'.\n\n"
                "Ejemplos válidos de cuadros clínicos:\n"
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
                "- Patrón emocional detectado\n\n"
                "Devolvé únicamente el nombre del cuadro clínico, sin explicaciones, ejemplos ni texto adicional."
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
                print(f"🧠 OpenAI asignó el cuadro clínico: {cuadro_asignado} para la emoción '{emocion}'.")
                
                # 🔄 Agregar el nuevo síntoma al set cacheado en memoria
                sintomas_cacheados.add(emocion.lower().strip())
                
                        
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
        
        # ✅ Registrar emociones en la base solo si aún no están registradas en esta interacción
        emociones_registradas_bd = obtener_emociones_ya_registradas(user_id, contador)
        
        for emocion in session["emociones_detectadas"]:
            if emocion not in emociones_registradas_bd:
                registrar_emocion(emocion, f"interacción {contador}", user_id)

        # 🧠 Detección de patrones reiterativos en interacciones 6 a 8
        if 6 <= contador <= 8:
            patron_detectado = inferir_patron_interactivo(session["mensajes"][-3:])
            if patron_detectado != "sin patrón consistente":
                print(f"🔄 Patrón interactivo detectado: {patron_detectado}")
        
        # ✅ En la interacción 5, generar resumen clínico y estado emocional predominante
        if contador == 5:
            respuesta = generar_resumen_interaccion_5(session, user_id, interaccion_id, contador)
            return {"respuesta": respuesta}
        
        if contador == 9:
            # ✅ Consolidar emociones de interacciones anteriores (1 a 5)
            for mensaje in session["mensajes"][:-4]:
                nuevas = detectar_emociones_negativas(mensaje) or []
                for emocion in nuevas:
                    emocion = emocion.lower().strip()
                    emocion = re.sub(r'[^\w\sáéíóúüñ]+$', '', emocion)
                    if emocion not in session["emociones_detectadas"]:
                        session["emociones_detectadas"].append(emocion)
        
            # 🧩 Generar resumen completo incluyendo nuevas emociones de interacciones 6 a 9
            respuesta = generar_resumen_interaccion_9(session, user_id, interaccion_id, contador)
            return {"respuesta": respuesta}

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
            "precio", "cuánto sale", "cuánto cuesta", "valor", "honorario", "cobra", "cobrás",
            "tarifa", "cuánto cobra", "cuanto cobra", "cuánto es", "sale la consulta", "vale la consulta",
            "cuánto cobran", "cuánto hay que pagar", "cuánto cuesta la consulta", "cuánto tengo que pagar"
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
                    + obtener_mensaje_contacto()
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
                    + obtener_mensaje_contacto()
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
                    "Para coordinar una sesión y consultar los medios de pago disponibles, "
                    + obtener_mensaje_contacto()
                )
            }
        
        
        # 🧩 Generar respuesta con OpenAI si no es la interacción 5, 9 o 10+
        saludo_inicio = "- Comenzá la respuesta con un saludo breve como “Hola, ¿qué tal?”.\n" if contador == 1 else ""
        
        prompt = (
            f"Mensaje recibido del usuario: '{mensaje_usuario}'.\n\n"
            "Redactá una respuesta breve, profesional y clínica como si fueras el asistente virtual del Lic. Daniel O. Bustamante, psicólogo.\n\n"
            "Estilo y directrices obligatorias:\n"
            "- Mantené un tono clínico, sobrio, profesional y respetuoso.\n"
            f"{saludo_inicio}"
            "- Si se detecta malestar emocional, formulá una observación objetiva con expresiones como: 'pareciera tratarse de...', 'podría vincularse a...', 'refiere a...' o 'se observa...'.\n"
            "- Evitá cualquier frase emocional simulada (ej: 'te entiendo', 'estás en buenas manos', 'no estás solo/a', 'tranquilo/a', etc.).\n"
            "- No uses frases motivacionales ni lenguaje coloquial (evitá: 'todo va a estar bien', 'contá conmigo', etc.).\n"
            "- No uses lenguaje institucional como 'nuestro equipo', 'desde nuestro espacio', 'trabajamos en conjunto', etc.\n"
            "- No brindes datos de contacto, precios, horarios, enlaces ni información administrativa, salvo que el usuario lo haya pedido explícitamente.\n"
            "- No recomiendes consultar con el Lic. Bustamante ni uses expresiones como 'consultar con un profesional', 'buscar ayuda especializada' u otras sugerencias implícitas.\n"
            "- No formules preguntas como “¿Deseás que te facilite información sobre agendar?” ni menciones WhatsApp.\n"
            "- No uses 'Estimado/a', ni encabezados de carta o email.\n"
            "- Solamente si el mensaje es claramente clínico, generá una respuesta analítica breve y profesional.\n"
            "- Si el mensaje no tiene contenido emocional o clínico relevante, devolvé una frase neutra como: 'Gracias por tu mensaje. ¿Hay algo puntual que te gustaría compartir o consultar en este espacio?'\n\n"
            "IMPORTANTE:\n"
            "- En las interacciones 5, 9 o 10+, podés aceptar que se mencione el contacto si fue solicitado.\n"
            "- En las demás interacciones (1 a 4), no lo menciones salvo que el usuario lo pida explícitamente.\n"
        )

        # ✅ Bloque de generación de respuesta clínica personalizada
        # Generación del prompt clínico personalizado según interacción
        prompt = (
            f"Mensaje recibido del usuario: '{mensaje_usuario}'.\n"
            "Redactá una respuesta breve, profesional y clínica como si fueras el asistente virtual del Lic. Daniel O. Bustamante, psicólogo.\n"
            "Estilo y directrices obligatorias:\n"
            "- Mantené un tono clínico, sobrio, profesional y respetuoso.\n"
            "- Comenzá la respuesta con un saludo breve como 'Hola, ¿qué tal?' solo si es la interacción 1.\n"
            "- Si se detecta malestar emocional, formulá una observación objetiva con expresiones como: 'se observa...', 'se advierte...', 'impresiona...', 'podría tratarse de...', 'da la sensación de ser...', 'normalmente se trata de un...', etc.\n"
            "- Evitá la frase 'Pareciera tratarse de...' en todas las interacciones, excepto en la 5 y 9.\n"
            "- En la interacción 1 usá la frase 'Se observa una vivencia de falta de sentido...'\n"
            "- No uses agradecimientos en ninguna interacción (ni al inicio ni al final).\n"
            "- No uses frases motivacionales ni simulaciones empáticas (ej: 'te entiendo', 'estás en buenas manos', etc.).\n"
            "- No uses lenguaje institucional ni expresiones como 'nuestro equipo', 'desde este espacio', etc.\n"
            "- No brindes datos de contacto, precios ni derivaciones, salvo que sea interacción 5, 9 o a partir de la 10.\n"
            "- Solo si el mensaje es claramente clínico, generá una respuesta analítica breve y profesional.\n"
            "- Si no tiene contenido clínico o emocional, devolvé una frase neutra: 'Gracias por tu mensaje. ¿Hay algo puntual que te gustaría compartir o consultar en este espacio?'\n"
            f"- IMPORTANTE: estás en la interacción {contador}.\n"
        )
        
        # Solicitar respuesta a OpenAI con el nuevo prompt clínico
        respuesta_original = generar_respuesta_con_openai(prompt, contador, user_id, mensaje_usuario, mensaje_original)
        
        # 🔍 Filtro para remover saludo 'Hola, ¿qué tal?' si no es la primera interacción
        if contador != 1 and respuesta_original.strip().lower().startswith("hola, ¿qué tal?"):
            respuesta_filtrada = respuesta_original.replace("Hola, ¿qué tal? ", "", 1).strip()
            motivo = "Se eliminó el saludo inicial 'Hola, ¿qué tal?' porque no corresponde repetirlo en interacciones posteriores a la primera"
            registrar_auditoria_respuesta(user_id, respuesta_original, respuesta_filtrada, motivo)
            respuesta_ai = respuesta_filtrada
        else:
            respuesta_ai = respuesta_original
        


        # 🔒 Filtro contra mención indebida al Lic. Bustamante fuera de interacciones permitidas
        if contador not in [5, 9] and contador < 10 and not es_consulta_contacto(mensaje_usuario, user_id, mensaje_original):
            if "bustamante" in respuesta_original.lower() or "+54 911 3310-1186" in respuesta_original:
                # Eliminar cualquier frase que mencione al Lic. Bustamante o su número
                respuesta_filtrada = re.sub(
                    r"(el Lic\.? Bustamante.*?[\.\!\?])",
                    "",
                    respuesta_original,
                    flags=re.IGNORECASE
                )
                motivo = "Mención indebida a contacto fuera de interacciones 5, 9 o 10+"
                registrar_auditoria_respuesta(user_id, respuesta_original, respuesta_filtrada.strip(), motivo)
                respuesta_ai = respuesta_filtrada.strip()
            else:
                respuesta_ai = respuesta_original
        else:
            respuesta_ai = respuesta_original

        # 🛑 Filtro para derivaciones implícitas indebidas
        frases_implicitas_derivacion = [
            "podrías trabajarlo con", "te sugiero considerarlo en una consulta",
            "evaluarlo con un profesional", "sería conveniente que lo converses",
            "hablarlo en un espacio terapéutico", "apoyo profesional", 
            "ayuda especializada", "espacio terapéutico", 
            "alguien capacitado", "profesional de la salud mental"
        ]
        
        if contador not in [5, 9] and contador < 10 and not es_consulta_contacto(mensaje_usuario, user_id, mensaje_original):
            for frase in frases_implicitas_derivacion:
                if frase in respuesta_original.lower():
                    motivo = "Derivación implícita fuera de interacción permitida"
                    respuesta_ai = (
                        "Gracias por tu mensaje. Si querés, podés contarme un poco más sobre lo que estás sintiendo "
                        "para poder continuar con el análisis clínico correspondiente."
                    )
                    registrar_auditoria_respuesta(user_id, respuesta_original, respuesta_ai, motivo)
                    break
                return {"respuesta": respuesta_ai}
        
        # 🔐 Seguridad textual: verificar si la respuesta de OpenAI contiene elementos peligrosos
        if contiene_elementos_peligrosos(respuesta_original):
            respuesta_ai = (
                "Por razones de seguridad, la respuesta generada fue descartada por contener elementos técnicos no permitidos. "
                "Podés intentar formular tu consulta de otra manera o escribir directamente al WhatsApp del Lic. Bustamante: +54 911 3310-1186."
            )
            registrar_auditoria_respuesta(user_id, respuesta_original, respuesta_ai, "Respuesta descartada por contener elementos peligrosos")
            return {"respuesta": respuesta_ai}

        
        # Validación previa
        if not respuesta_original:
            respuesta_ai = (
                "Lo siento, hubo un inconveniente al generar una respuesta automática. Podés escribirle al Lic. Bustamante al WhatsApp +54 911 3310-1186."
            )
            registrar_auditoria_respuesta(user_id, "Error al generar respuesta", respuesta_ai, "Error: OpenAI devolvió respuesta vacía")
            return {"respuesta": respuesta_ai}
        
        respuesta_ai = respuesta_original  # Copia editable
        motivo = None

        # 🔍 Filtro para lenguaje institucional
        palabras_prohibidas = ["nosotros", "nuestro equipo", "nuestra institución", "desde nuestra", "trabajamos en conjunto"]
        if any(palabra in respuesta_ai.lower() for palabra in palabras_prohibidas):
            respuesta_ai = (
                "Gracias por tu consulta. El Lic. Daniel O. Bustamante estará encantado de ayudarte. "
                "Podés escribirle directamente al WhatsApp +54 911 3310-1186 para obtener más información."
            )

        # 🔍 Filtro para lenguaje empático simulado o genérico prohibido
        frases_empaticas_simuladas = [
            "estoy aquí para ayudarte", "estoy aquí para ayudarle", "te puedo ayudar", 
            "estamos para ayudarte", "cuente conmigo", "puedo ayudarte", 
            "tranquilo", "no estás solo", "estás en buenas manos", 
            "todo va a estar bien", "puede contar conmigo"
        ]
        if any(frase in respuesta_ai.lower() for frase in frases_empaticas_simuladas):
            respuesta_ai = (
                "Gracias por tu mensaje. Si querés, podés contarme un poco más sobre lo que estás atravesando "
                "para poder continuar con el análisis clínico correspondiente."
            )
            motivo = "Frase empática simulada detectada y reemplazada"

        
        # 🔍 Filtro para desvíos temáticos (por si OpenAI habla de finanzas o cosas raras)
        temas_prohibidos = ["finanzas", "inversiones", "educación financiera", "consultoría financiera", "legal", "técnico"]
        if any(tema in respuesta_ai.lower() for tema in temas_prohibidos):
            respuesta_ai = (
                "El Lic. Daniel O. Bustamante es psicólogo clínico. Si querés saber más sobre los servicios que ofrece, "
                + obtener_mensaje_contacto() +
                " y te brindará toda la información necesaria."
            )

        # 🔍 Filtro para eliminar encabezados como “Estimado/a usuario/a”
        if respuesta_original.lower().startswith("estimado") or "estimado/a" in respuesta_original.lower():
            respuesta_original = re.sub(r"(?i)^estimado/a\s+usuario/a,?\s*", "", respuesta_original).strip()

        
        # 🔍 Reemplazo de marcador si quedó en la respuesta
        respuesta_ai = respuesta_ai.replace("[Incluir número de contacto]", "+54 911 3310-1186")

        # 🛡️ Filtrado de precios por si OpenAI menciona algún valor numérico
        if any(palabra in respuesta_ai.lower() for palabra in ["$", "usd", "euros", "€", "dólares", "pesos", "cuesta", "sale", "vale", "precio", "tarifa", "honorario", "paga", "cobra", "cobro"]):
            respuesta_ai = (
                "Sobre los valores de la consulta, te sugiero contactar directamente al Lic. Daniel O. Bustamante. "
                + obtener_mensaje_contacto() +
                " para obtener esa información de manera personalizada."
            )
            # 🧾 Auditoría: log si OpenAI intentó responder con precios
            print("⚠️ Se interceptó una respuesta con posible contenido de precios y fue reemplazada para evitar brindar esa información.")

        # ❌ Interceptar frases ambiguas que sugieran contacto antes de la interacción 5
        if contador <= 4:
            frases_implicitas = [
                "si lo desea puedo brindarle más información",
                "si desea más información",
                "puedo brindarle más detalles si lo necesita",
                "si quiere puedo contarle más",
                "estoy aquí para ayudarle",
                "podría ayudarle si lo desea",
                "si desea saber más"
            ]
            if any(f in respuesta_ai.lower() for f in frases_implicitas):
                respuesta_ai = (
                    "Gracias por tu mensaje. En este espacio se brinda orientación clínica general. "
                    "¿Querés contarme un poco más sobre lo que estás sintiendo para poder ayudarte mejor?"
                )
                motivo = "Frase ambigua de sugerencia de contacto detectada en interacción temprana"


        # Detectar modificaciones y registrar auditoría
        if respuesta_original != respuesta_ai:
            motivo = "Respuesta modificada por contener lenguaje institucional, temáticas no permitidas o precios"
            registrar_auditoria_respuesta(user_id, respuesta_original, respuesta_ai, motivo)
        else:
            registrar_auditoria_respuesta(user_id, respuesta_original, respuesta_ai)

        # Usar el ID de interacción previamente registrado para guardar la respuesta
        registrar_respuesta_openai(interaccion_id, respuesta_ai)

        # ❌ Filtrado final de menciones indebidas al Lic. Bustamante antes de interacción 5
        if "bustamante" in respuesta_ai.lower() and contador not in [5, 9] and contador < 10 and not es_consulta_contacto(mensaje_usuario, user_id, mensaje_original):
            respuesta_filtrada = re.sub(r"(?i)con (el )?Lic(\.|enciado)? Daniel O\.? Bustamante.*?(\.|\n|$)", "", respuesta_ai)
            motivo = "Se eliminó mención indebida al Lic. Bustamante antes de interacción permitida"
            registrar_auditoria_respuesta(user_id, respuesta_original, respuesta_filtrada, motivo)
            return {"respuesta": respuesta_filtrada}
        
        return {"respuesta": respuesta_ai}

    except Exception as e:
        print(f"❌ Error inesperado en el endpoint /asistente: {e}")
        return {
            "respuesta": (
                "Ocurrió un error al procesar tu solicitud. Podés intentarlo nuevamente más tarde "
                "o escribirle al Lic. Bustamante por WhatsApp: +54 911 3310-1186."
            )
        }



#------------------ SCRIPT DE PRUEBA DE IMPORTACION CORRECTA DE LOS IMPORT--- LUEGO ELIMINAR ESTE SCRIPT-----------------

from fastapi.responses import HTMLResponse

@app.get("/verificar-imports", response_class=HTMLResponse)
async def verificar_imports():
    return HTMLResponse(content="""
    <html>
    <head><title>Verificación de Imports</title></head>
    <body>
        <h2>🔍 Verificación manual de imports desde <code>core.db</code></h2>
        <ul>
            <li><strong>✔️ registro.py:</strong>
                <ul>
                    <li>registrar_emocion</li>
                    <li>registrar_interaccion</li>
                    <li>registrar_respuesta_openai</li>
                    <li>registrar_auditoria_input_original</li>
                    <li>registrar_similitud_semantica</li>
                    <li>registrar_log_similitud</li>
                    <li>registrar_auditoria_respuesta</li>
                    <li>registrar_inferencia</li>
                </ul>
            </li>
            <li><strong>✔️ sintomas.py:</strong>
                <ul>
                    <li>registrar_sintoma</li>
                    <li>actualizar_sintomas_sin_estado_emocional</li>
                    <li>obtener_sintomas_existentes</li>
                    <li>obtener_sintomas_con_estado_emocional</li>
                    <li>obtener_coincidencias_sintomas_y_registrar</li>
                </ul>
            </li>
        </ul>
        <p>📌 Si alguna de estas funciones está definida en <code>app.py</code> en lugar de ser importada desde <code>core.db</code>, deberías moverla para evitar duplicación.</p>
    </body>
    </html>
    """)

