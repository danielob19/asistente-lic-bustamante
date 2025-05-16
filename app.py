# 📦 Módulos estándar de Python
import os
import time
import threading
import random
import re
from datetime import datetime, timedelta
from collections import Counter
from typing import List, Optional  # ✅ Agregado para evitar NameError

# 🧪 Librerías externas
import psycopg2
from psycopg2 import sql
import numpy as np
import openai
from pydantic import BaseModel

# 🚀 Framework FastAPI
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

# 🧠 Diccionario de sesiones por usuario (en memoria)
user_sessions = {}

from cerebro_simulado import (
    predecir_evento_futuro,
    inferir_patron_interactivo,
    evaluar_coherencia_mensaje,
    clasificar_estado_mental,
    inferir_intencion_usuario
)

# ========================== CONSTANTES DE CLASIFICACIÓN ==========================

CLINICO_CONTINUACION = "CLINICO_CONTINUACION"
SALUDO = "SALUDO"
CORTESIA = "CORTESIA"
ADMINISTRATIVO = "ADMINISTRATIVO"
CLINICO = "CLINICO"
CONSULTA_AGENDAR = "CONSULTA_AGENDAR"
CONSULTA_MODALIDAD = "CONSULTA_MODALIDAD"

def es_consulta_contacto(mensaje: str, user_id: str = None, mensaje_original: str = None) -> bool:
    """
    Detecta si el mensaje hace referencia al deseo de contactar al profesional.
    Si hay coincidencia y se proporciona `user_id` y `mensaje_original`, registra la auditoría automáticamente.
    """
    if not mensaje or not isinstance(mensaje, str):
        return False

    mensaje = mensaje.lower()

    expresiones_contacto = [
        "contacto", "numero", "número", "whatsapp", "teléfono", "telefono",
        "como lo contacto", "quiero contactarlo", "como me comunico",
        "quiero escribirle", "quiero hablar con él", "me das el número",
        "como se agenda", "como saco turno", "quiero pedir turno",
        "necesito contactarlo", "como empiezo la terapia", "quiero empezar la consulta",
        "como me comunico con el licenciado", "mejor psicologo", "mejor terapeuta",
        "atienden estos casos", "atiende casos", "trata casos", "atiende temas",
        "trata temas", "atiende estos", "trata estos", "atiende estos temas"
    ]

    hay_coincidencia = any(exp in mensaje for exp in expresiones_contacto)

    if hay_coincidencia and user_id and mensaje_original:
        registrar_auditoria_input_original(user_id, mensaje_original, mensaje, "CONSULTA_CONTACTO")

    return hay_coincidencia

# ✅ Función reutilizable de seguridad textual
def contiene_elementos_peligrosos(texto: str) -> bool:
    """
    Detecta si un texto contiene patrones potencialmente peligrosos o maliciosos
    como comandos de sistema, código fuente o expresiones técnicas sensibles.
    """
    patrones_riesgosos = [
        r"openai\.api_key", r"import\s", r"os\.system", r"eval\(", r"exec\(",
        r"<script", r"</script>", r"\bdrop\b.*\btable\b", r"\bdelete\b.*\bfrom\b",
        r"\brm\s+-rf\b", r"\bchmod\b", r"\bmkfs\b", r"\bshutdown\b", r"\breboot\b",
        r"SELECT\s+.*\s+FROM", r"INSERT\s+INTO", r"UPDATE\s+\w+\s+SET", r"DELETE\s+FROM"
    ]
    return any(re.search(patron, texto, re.IGNORECASE) for patron in patrones_riesgosos)

# 📞 Función centralizada para mensaje de contacto
def obtener_mensaje_contacto():
    return (
        "En caso de que desees contactar al Lic. Daniel O. Bustamante, "
        "podés hacerlo escribiéndole al WhatsApp +54 911 3310-1186, que con gusto responderá a tus inquietudes."
    )


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
            + obtener_mensaje_contacto()
        )
    },
    {
        "pregunta": "¿Cuánto dura la sesión?",
        "respuesta": (
            "Las sesiones con el Lic. Daniel O. Bustamante tienen una duración aproximada de 50 minutos y se realizan por videoconsulta.\n\n"
            "La frecuencia puede variar según cada caso, pero generalmente se recomienda un encuentro semanal para favorecer el proceso terapéutico.\n\n"
            + obtener_mensaje_contacto()
        )
    },
    {
        "pregunta": "¿Trabaja con obras sociales?",
        "respuesta": (
            "El Lic. Daniel O. Bustamante no trabaja con obras sociales ni prepagas. Atiende únicamente de manera particular. "
            + obtener_mensaje_contacto()
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

def buscar_respuesta_semantica_con_score(mensaje: str, umbral=0.88):
    try:
        embedding_usuario = openai.Embedding.create(
            model="text-embedding-ada-002",
            input=mensaje
        )["data"][0]["embedding"]
        embedding_usuario = np.array(embedding_usuario)

        mejor_score = 0
        mejor_pregunta = None
        mejor_respuesta = None

        for item in faq_respuestas:
            emb_faq = item.get("embedding")
            if emb_faq is not None:
                similitud = np.dot(embedding_usuario, emb_faq) / (norm(embedding_usuario) * norm(emb_faq))
                if similitud > mejor_score:
                    mejor_score = similitud
                    mejor_pregunta = item["pregunta"]
                    mejor_respuesta = item["respuesta"]

        if mejor_score >= umbral:
            return mejor_pregunta, mejor_respuesta, mejor_score
        return None

    except Exception as e:
        print(f"❌ Error en buscar_respuesta_semantica_con_score: {e}")
        return None

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

# ===================== OPERACIONES CLÍNICAS SOBRE 'palabras_clave' =====================

# Registrar un síntoma con cuadro clínico asignado por OpenAI si no se proporciona
def registrar_sintoma(sintoma: str, estado_emocional: str = None):
    """
    Registra un síntoma en la base de datos con su estado emocional.
    Si no se proporciona un estado, lo clasifica automáticamente con OpenAI.
    """

    # Si no se proporciona un estado emocional, usar OpenAI para asignarlo
    if not estado_emocional or not estado_emocional.strip():
        try:
            prompt = (
                f"Asigna un estado emocional clínicamente relevante a la siguiente emoción o síntoma: '{sintoma}'.\n\n"
                "Seleccioná un estado con base en categorías clínicas como trastornos, síndromes o patrones emocionales reconocidos.\n\n"
                "Si no corresponde a ninguno en particular, clasificá como 'Patrón emocional detectado'.\n\n"
                "Respondé exclusivamente con el nombre del estado, sin explicaciones.\n\n"
                "Ejemplos válidos:\n"
                "- Trastorno de ansiedad\n"
                "- Cuadro de depresión\n"
                "- Estrés postraumático\n"
                "- Baja autoestima\n"
                "- Desgaste emocional\n"
                "- Sentimientos de inutilidad\n"
                "- Trastorno de impulsividad\n"
                "- Insomnio crónico\n"
                "- Patrón emocional detectado"
            )

            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50,
                temperature=0
            )

            estado_emocional = response.choices[0].message["content"].strip()

            if not estado_emocional:
                print(f"⚠️ OpenAI devolvió vacío. Se asignará 'Patrón emocional detectado' para '{sintoma}'.")
                estado_emocional = "Patrón emocional detectado"

            print(f"🧠 OpenAI asignó el estado emocional: {estado_emocional} para '{sintoma}'.")

        except Exception as e:
            print(f"❌ Error al clasificar '{sintoma}' con OpenAI: {e}")
            estado_emocional = "Patrón emocional detectado"

    # Insertar o actualizar en la base de datos
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO palabras_clave (sintoma, estado_emocional)
            VALUES (%s, %s)
            ON CONFLICT (sintoma) DO UPDATE SET estado_emocional = EXCLUDED.estado_emocional;
        """, (sintoma.strip().lower(), estado_emocional))
        conn.commit()
        conn.close()
        print(f"✅ Síntoma '{sintoma}' registrado con estado emocional '{estado_emocional}'.")
    except Exception as e:
        print(f"❌ Error al registrar síntoma '{sintoma}' en la base: {e}")

def actualizar_sintomas_sin_estado_emocional():
    """
    Busca síntomas en la base de datos que no tienen estado_emocional asignado,
    les solicita una clasificación clínica a OpenAI y actualiza la tabla.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        # Obtener síntomas sin estado emocional asignado
        cursor.execute("SELECT sintoma FROM palabras_clave WHERE estado_emocional IS NULL;")
        sintomas_pendientes = [row[0] for row in cursor.fetchall()]
        conn.close()

        if not sintomas_pendientes:
            print("✅ No hay síntomas pendientes de clasificación en estado_emocional.")
            return

        print(f"🔍 Clasificando {len(sintomas_pendientes)} síntomas sin estado_emocional...")

        for sintoma in sintomas_pendientes:
            prompt = (
                f"Asigná un estado emocional clínico adecuado al siguiente síntoma: '{sintoma}'.\n\n"
                "Seleccioná un estado emocional clínico compatible con clasificaciones como: Trastorno de ansiedad, Depresión mayor, Estrés postraumático, "
                "Trastorno de pánico, Baja autoestima, Desgaste emocional, Sentimientos de aislamiento, Insomnio crónico, etc.\n\n"
                "Si el síntoma no se vincula a un estado clínico específico, respondé con: 'Patrón emocional detectado'.\n\n"
                "Devolvé exclusivamente el nombre del estado emocional sin texto adicional ni explicaciones."
            )

            try:
                respuesta = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=50,
                    temperature=0.0
                )

                estado_emocional = respuesta["choices"][0]["message"]["content"].strip()
                print(f"📌 Estado emocional para '{sintoma}': {estado_emocional}")

                # Actualizar en la base de datos
                conn = psycopg2.connect(DATABASE_URL)
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE palabras_clave SET estado_emocional = %s WHERE sintoma = %s;",
                    (estado_emocional, sintoma)
                )
                conn.commit()
                conn.close()

            except Exception as e:
                print(f"⚠️ Error al clasificar o actualizar '{sintoma}': {e}")

    except Exception as e:
        print(f"❌ Error al conectar con la base de datos para actualizar estado_emocional: {e}")

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

# ===================== REGISTRO DE EMOCIONES DETECTADAS =====================

def registrar_emocion(emocion: str, contexto: str, user_id: str = None):
    """
    Registra una emoción detectada en la base de datos PostgreSQL.
    Si ya existe, actualiza el contexto concatenando. Si no existe, la inserta.
    Si la tabla tiene una columna 'user_id', se registra también.
    """
    try:
        print("\n======= 📌 REGISTRO DE EMOCIÓN DETECTADA =======")
        print(f"🧠 Emoción detectada: {emocion}")
        print(f"🧾 Contexto asociado: {contexto}")
        print(f"👤 Usuario: {user_id if user_id else 'No especificado'}")

        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cursor:
                # Verifica si la columna user_id existe
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'emociones_detectadas' AND column_name = 'user_id';
                """)
                tiene_user_id = bool(cursor.fetchone())

                # Verifica si ya existe una emoción con o sin user_id
                if tiene_user_id and user_id:
                    cursor.execute(
                        "SELECT contexto FROM emociones_detectadas WHERE emocion = %s AND user_id = %s;",
                        (emocion.strip().lower(), user_id)
                    )
                else:
                    cursor.execute(
                        "SELECT contexto FROM emociones_detectadas WHERE emocion = %s;",
                        (emocion.strip().lower(),)
                    )

                resultado = cursor.fetchone()

                if resultado:
                    nuevo_contexto = f"{resultado[0]}; {contexto.strip()}"
                    if tiene_user_id and user_id:
                        cursor.execute(
                            "UPDATE emociones_detectadas SET contexto = %s WHERE emocion = %s AND user_id = %s;",
                            (nuevo_contexto, emocion.strip().lower(), user_id)
                        )
                    else:
                        cursor.execute(
                            "UPDATE emociones_detectadas SET contexto = %s WHERE emocion = %s;",
                            (nuevo_contexto, emocion.strip().lower())
                        )
                    print("🔄 Emoción existente. Contexto actualizado.")
                else:
                    if tiene_user_id and user_id:
                        cursor.execute(
                            "INSERT INTO emociones_detectadas (emocion, contexto, user_id) VALUES (%s, %s, %s);",
                            (emocion.strip().lower(), contexto.strip(), user_id)
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO emociones_detectadas (emocion, contexto) VALUES (%s, %s);",
                            (emocion.strip().lower(), contexto.strip())
                        )
                    print("🆕 Nueva emoción registrada exitosamente.")

                conn.commit()

        print("===============================================\n")

    except Exception as e:
        print(f"❌ Error al registrar emoción '{emocion}': {e}")



# ===================== REGISTRO DE INTERACCIONES Y RESPUESTAS =====================

# Registrar una interacción (versión extendida)
def registrar_interaccion(user_id: str, consulta: str, mensaje_original: str = None):
    try:
        print("\n===== DEPURACIÓN - REGISTRO DE INTERACCIÓN =====")
        print(f"Intentando registrar interacción: user_id={user_id}")
        print(f"Consulta purificada: {consulta}")
        print(f"Mensaje original: {mensaje_original}")

        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        # Verifica si la columna "mensaje_original" existe; si no, la crea automáticamente
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'interacciones' AND column_name = 'mensaje_original';
        """)
        columna_existente = cursor.fetchone()

        if not columna_existente:
            print("⚠️ La columna 'mensaje_original' no existe. Creándola...")
            cursor.execute("ALTER TABLE interacciones ADD COLUMN mensaje_original TEXT;")
            conn.commit()

        # Inserta la interacción con el mensaje original
        cursor.execute("""
            INSERT INTO interacciones (user_id, consulta, mensaje_original) 
            VALUES (%s, %s, %s) RETURNING id;
        """, (user_id, consulta, mensaje_original))
        
        interaccion_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()

        print(f"✅ Interacción registrada con éxito. ID asignado: {interaccion_id}\n")
        return interaccion_id

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


def registrar_auditoria_input_original(user_id: str, mensaje_original: str, mensaje_purificado: str, clasificacion: str = None):
    """
    Registra el input original, su versión purificada y la clasificación contextual (opcional) en una tabla de auditoría.
    Permite trazabilidad entre lo que dijo el usuario y cómo fue interpretado.
    """
    try:
        print("\n📋 Registrando input original y purificado en auditoría")
        print(f"👤 user_id: {user_id}")
        print(f"📝 Original: {mensaje_original}")
        print(f"🧼 Purificado: {mensaje_purificado}")
        print(f"🏷️ Clasificación: {clasificacion}")

        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        # Crear tabla si no existe, con columna de clasificación incluida
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auditoria_input_original (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                mensaje_original TEXT NOT NULL,
                mensaje_purificado TEXT NOT NULL,
                clasificacion TEXT,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Insertar datos con clasificación
        cursor.execute("""
            INSERT INTO auditoria_input_original (
                user_id, mensaje_original, mensaje_purificado, clasificacion
            ) VALUES (%s, %s, %s, %s);
        """, (user_id, mensaje_original.strip(), mensaje_purificado.strip(), clasificacion))

        conn.commit()
        conn.close()
        print("✅ Auditoría registrada exitosamente.\n")

    except Exception as e:
        print(f"❌ Error al registrar auditoría del input original: {e}")


# Registrar una similitud semántica en la base de datos
def registrar_similitud_semantica(user_id: str, consulta: str, pregunta_faq: str, similitud: float):
    """
    Registra la similitud semántica en la tabla faq_similitud_logs.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO faq_similitud_logs (user_id, consulta, pregunta_faq, similitud)
            VALUES (%s, %s, %s, %s);
        """, (user_id, consulta, pregunta_faq, similitud))

        conn.commit()
        conn.close()
        print(f"🧠 Similitud registrada con éxito (Score: {similitud}) para FAQ: '{pregunta_faq}'\n")

    except Exception as e:
        print(f"❌ Error al registrar similitud semántica: {e}")

def registrar_inferencia(user_id: str, interaccion_id: int, tipo: str, valor: str):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO inferencias_cerebro_simulado (user_id, interaccion_id, tipo, valor)
            VALUES (%s, %s, %s, %s);
        """, (user_id, interaccion_id, tipo, valor))

        conn.commit()
        conn.close()
        print(f"🧠 Inferencia registrada: [{tipo}] → {valor}")

    except Exception as e:
        print(f"❌ Error al registrar inferencia: {e}")


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

def clasificar_input_inicial(texto: str) -> str:
    if not texto or not isinstance(texto, str):
        return "OTRO"

    texto = texto.lower().strip()

    # 🧠 Cargar síntomas desde la BD si el set global está vacío
    global sintomas_cacheados
    if not sintomas_cacheados:
        try:
            sintomas_existentes = obtener_sintomas_existentes()
            sintomas_cacheados.update(sintomas_existentes)
        except Exception as e:
            print(f"❌ Error al cargar síntomas cacheados en clasificar_input_inicial: {e}")

    # 👋 Saludos y detección combinada con malestar clínico
    saludos = ["hola", "buenos días", "buenas tardes", "buenas noches", "qué tal", "como estás", "como esta"]
    if any(s in texto for s in saludos) and es_tema_clinico_o_emocional(texto):
        return "CLINICO"
    if texto in saludos:
        return "SALUDO"

    # 🙏 Frases de agradecimiento o cortesía
    expresiones_cortesia = [
        "gracias", "muchas gracias", "muy amable", "ok gracias", "perfecto, gracias", "mil gracias",
        "te agradezco", "todo bien", "no necesito más", "me quedó claro", "nada más"
    ]
    if texto in expresiones_cortesia:
        return "CORTESIA"

    # 🔎 Consultas sobre modalidad de atención (ubicación, virtualidad)
    consultas_modalidad = [
        "es presencial", "es online", "son online", "es virtual", "atiende por videollamada", "por zoom",
        "se hace por videollamada", "atención virtual", "por llamada", "me tengo que presentar",
        "se hace presencial", "ubicación", "dónde atiende", "donde atiende", "donde queda",
        "dónde está", "ciudad", "zona", "provincia", "en qué parte estás", "dónde es la consulta",
        "dirección", "en qué lugar se atiende", "dónde se realiza", "debo ir al consultorio",
        "se hace a distancia", "atención remota", "consultorio", "atención online"
    ]
    if any(frase in texto for frase in consultas_modalidad):
        return "CONSULTA_MODALIDAD"

    # 🧠 Malestar clínico directo (abstracciones y síntomas)
    clinicos_ampliados = [
        "nada me entusiasma", "nada me importa", "nada tiene sentido", "no tengo ganas", "no me interesa nada",
        "no me dan ganas", "no siento nada", "me quiero morir", "pienso en morirme", "me siento vacío", "no le encuentro sentido",
        "todo me supera", "ya no disfruto", "siento un peso", "me cuesta levantarme", "lloro sin razón", "me duele el alma",
        "estoy muy triste", "me siento solo", "no puedo más", "no puedo dormir", "siento ansiedad", "me siento mal conmigo"
    ]
    if any(frase in texto for frase in clinicos_ampliados):
        return "CLINICO"

    # 🧾 Consultas clínicas explícitas disfrazadas de preguntas
    frases_consulta_directa = [
        "¿atienden estos casos?", "¿atiende estos casos?", "¿atienden el caso?", "¿atiende el caso?",
        "¿tratan este tipo de temas?", "¿trata este tipo de temas?",
        "¿manejan este tipo de situaciones?", "¿manejan estos casos?",
        "¿hacen tratamiento de esto?", "¿hace tratamiento de esto?",
        "¿el licenciado puede atender esto?", "¿pueden ayudar con esto?",
        "¿esto lo trata el profesional?", "¿esto lo trabajan en terapia?",
        "¿esto se trabaja en terapia?", "¿este tema lo abordan?"
    ]
    if any(frase in texto for frase in frases_consulta_directa):
        return "ADMINISTRATIVO"

    # 📋 Consultas indirectas: verbo + tema clínico (frecuentes en landing pages)
    temas_clinicos_comunes = [
        "terapia de pareja", "psicoterapia", "tratamiento psicológico", "consultas psicológicas",
        "abordaje emocional", "tratamiento emocional", "atención psicológica"
    ]
    for verbo in [
        "hace", "hacen", "dan", "atiende", "atienden", "realiza", "realizan", "ofrece", "ofrecen",
        "trabaja con", "trabajan con", "brinda", "brindan"
    ]:
        for tema in temas_clinicos_comunes:
            patron = rf"{verbo}\s*(el|la|los|las)?\s*{re.escape(tema)}"
            if re.search(patron, texto, re.IGNORECASE):
                registrar_auditoria_input_original(
                    user_id="sistema",
                    mensaje_original=texto,
                    mensaje_purificado=texto,
                    clasificacion="ADMINISTRATIVO (verbo + tema clínico común)"
                )
                return "ADMINISTRATIVO"

    # 🧠 Consultas indirectas sobre síntomas mediante verbos + síntomas cacheados
    verbos_consulta = [
        "trata", "tratan", "atiende", "atienden", "aborda", "abordan",
        "se ocupa de", "se ocupan de", "interviene en", "intervienen en",
        "trabaja con", "trabajan con", "hace tratamiento de", "hacen tratamiento de",
        "realiza tratamiento de", "realizan tratamiento de",
        "da tratamiento a", "dan tratamiento a", "maneja", "manejan",
        "ayuda con", "ayudan con", "acompaña en", "acompañan en",
        "resuelve", "resuelven", "puede tratar", "pueden tratar",
        "puede ayudar con", "pueden ayudar con", "atiende el tema de", "trata el tema de",
        "puede atender", "pueden atender", "está capacitado para tratar", "están capacitados para tratar"
    ]
    for verbo in verbos_consulta:
        for sintoma in sintomas_cacheados:
            if verbo in texto and sintoma in texto:
                return "ADMINISTRATIVO"

    # 🧠 Evaluación final: si el mensaje contiene síntomas o malestar
    if es_tema_clinico_o_emocional(texto):
        return "CLINICO"

    return "OTRO"


    # Expresiones típicas de saludo
    saludos = ["hola", "buenas", "buenos días", "buenas tardes", "buenas noches", "qué tal", "como estás", "como esta"]
    if any(frase in texto for frase in saludos):
        return "SALUDO"

    # Frases de agradecimiento o cierre amable
    cortesias = ["gracias", "muy amable", "te agradezco", "muchas gracias", "ok gracias", "perfecto, gracias", "mil gracias", "gracias por todo"]
    if any(frase in texto for frase in cortesias):
        return "CORTESIA"

    # Consultas sobre modalidad de atención (online/presencial) o ubicación
    consultas_modalidad = [
        "es presencial", "es online", "son online", "es virtual", "atiende por videollamada", "por zoom",
        "se hace por videollamada", "atención virtual", "por llamada", "me tengo que presentar",
        "se hace presencial", "ubicación", "dónde atiende", "donde atiende", "donde queda",
        "dónde está", "ciudad", "zona", "provincia", "en qué parte estás", "dónde es la consulta",
        "dirección", "en qué lugar se atiende", "dónde se realiza", "debo ir al consultorio",
        "se hace a distancia", "atención remota", "consultorio", "atención online"
    ]
    
    if any(frase in texto for frase in consultas_modalidad):
        return "CONSULTA_MODALIDAD"

    
    # 🧠 Consultas indirectas sobre si se tratan ciertos cuadros emocionales usando síntomas cacheados
    verbos_consulta = [
        "trata", "tratan", "atiende", "atienden", "aborda", "abordan",
        "se ocupa de", "se ocupan de", "interviene en", "intervienen en",
        "trabaja con", "trabajan con", "hace tratamiento de", "hacen tratamiento de",
        "realiza tratamiento de", "realizan tratamiento de",
        "da tratamiento a", "dan tratamiento a", "maneja", "manejan",
        "ayuda con", "ayudan con", "acompaña en", "acompañan en",
        "resuelve", "resuelven", "puede tratar", "pueden tratar",
        "puede ayudar con", "pueden ayudar con", "atiende el tema de", "trata el tema de",
        "puede atender", "pueden atender", "está capacitado para tratar", "están capacitados para tratar"
    ]
    
    # Frases interrogativas comunes que implican consulta clínica
    frases_consulta_directa = [
        "¿atienden estos casos?", "¿atiende estos casos?", "¿atienden el caso?", "¿atiende el caso?",
        "¿tratan este tipo de temas?", "¿trata este tipo de temas?",
        "¿manejan este tipo de situaciones?", "¿manejan estos casos?",
        "¿hacen tratamiento de esto?", "¿hace tratamiento de esto?",
        "¿el licenciado puede atender esto?", "¿pueden ayudar con esto?",
        "¿esto lo trata el profesional?", "¿esto lo trabajan en terapia?",
        "¿esto se trabaja en terapia?", "¿este tema lo abordan?"
    ]
    if any(frase in texto.lower() for frase in frases_consulta_directa):
        return "ADMINISTRATIVO"

    # Indicadores clínicos ampliados (incluso con negaciones o abstracciones emocionales)
    clinicos_ampliados = [
        "nada me entusiasma", "nada me importa", "nada tiene sentido", "no tengo ganas", "no me interesa nada",
        "no me dan ganas", "no siento nada", "me quiero morir", "pienso en morirme", "me siento vacío", "no le encuentro sentido",
        "todo me supera", "ya no disfruto", "siento un peso", "me cuesta levantarme", "lloro sin razón", "me duele el alma",
        "estoy muy triste", "me siento solo", "no puedo más", "no puedo dormir", "siento ansiedad", "me siento mal conmigo"
    ]
    if any(frase in texto for frase in clinicos_ampliados):
        return "CLINICO"

        # Verbos comunes que indican consulta sobre si se atienden determinados temas clínicos
    verbos_tratamiento = [
        "tratan", "atienden", "hacen", "realizan", "abordan", "se ocupan", 
        "manejan", "intervienen en", "trabajan con", "ayudan con", "dan tratamiento a"
    ]

    # Cargar dinámicamente los síntomas registrados en la base
    try:
        sintomas_existentes = obtener_sintomas_existentes()
    except Exception as e:
        print(f"⚠️ Error al obtener síntomas desde la base en clasificar_input_inicial: {e}")
        sintomas_existentes = []

    return "OTRO"


def obtener_sintomas_con_estado_emocional():
    """
    Devuelve una lista de tuplas (sintoma, estado_emocional) desde la base de datos.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT LOWER(sintoma), estado_emocional FROM palabras_clave")
        resultados = cursor.fetchall()
        conn.close()
        return resultados
    except Exception as e:
        print(f"❌ Error al obtener síntomas con estado emocional: {e}")
        return []

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
    Busca coincidencias de síntomas en la base de datos y devuelve una lista de estados emocionales relacionados.
    Si una emoción no tiene coincidencias exactas ni parciales, la registra en la base de datos para futura clasificación.
    Luego, usa OpenAI para clasificar cualquier síntoma sin estado emocional asignado y lo actualiza en la base de datos.
    """
    if not emociones:
        return []

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        print("\n===== DEPURACIÓN SQL =====")
        print("Emociones detectadas:", emociones)

        # Buscar coincidencias exactas en la base de datos
        consulta = "SELECT sintoma, estado_emocional FROM palabras_clave WHERE sintoma = ANY(%s)"
        cursor.execute(consulta, (emociones,))
        resultados = cursor.fetchall()

        estados_emocionales = [resultado[1] for resultado in resultados]
        sintomas_existentes = [resultado[0] for resultado in resultados]

        print("Síntomas encontrados en la BD:", sintomas_existentes)
        print("Estados emocionales encontrados:", estados_emocionales)

        # Identificar emociones que no están en la base de datos y registrarlas sin estado emocional
        emociones_nuevas = [emocion for emocion in emociones if emocion not in sintomas_existentes]
        for emocion in emociones_nuevas:
            registrar_sintoma(emocion, None)  # Se registra sin estado emocional

        conn.commit()
        conn.close()

        # Ahora clasificamos los síntomas que se registraron sin estado emocional
        actualizar_sintomas_sin_estado_emocional()

        return estados_emocionales if estados_emocionales else []

    except Exception as e:
        print(f"❌ Error al obtener coincidencias de síntomas o registrar nuevos síntomas: {e}")
        return []

def obtener_emociones_ya_registradas(user_id, interaccion_id):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("""
            SELECT emocion FROM emociones_detectadas
            WHERE user_id = %s AND contexto = %s
        """, (user_id, f"interacción {interaccion_id}"))
        resultados = cur.fetchall()
        emociones = [r[0].lower().strip() for r in resultados]
        cur.close()
        conn.close()
        return emociones
    except Exception as e:
        print(f"❌ Error al obtener emociones ya registradas en la BD: {e}")
        return []

def obtener_combinaciones_no_registradas(dias=7):
    """
    Devuelve una lista de combinaciones emocionales detectadas por el bot pero que aún no tienen frase registrada.
    Por defecto, muestra las registradas en los últimos 'dias' (7 por defecto).
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        # Calcular fecha límite
        fecha_limite = datetime.now() - timedelta(days=dias)

        consulta = """
            SELECT emocion_1, emocion_2, fecha 
            FROM combinaciones_no_registradas
            WHERE fecha >= %s
            ORDER BY fecha DESC;
        """
        cursor.execute(consulta, (fecha_limite,))
        combinaciones = cursor.fetchall()
        conn.close()

        print(f"\n📋 Combinaciones emocionales no registradas (últimos {dias} días):")
        for emocion_1, emocion_2, fecha in combinaciones:
            print(f" - {emocion_1} + {emocion_2} → {fecha.strftime('%Y-%m-%d %H:%M')}")

        return combinaciones

    except Exception as e:
        print(f"❌ Error al obtener combinaciones no registradas: {e}")
        return []

# ===================== REGISTRO DE SIMILITUD SEMÁNTICA =====================

def registrar_log_similitud(user_id: str, consulta: str, pregunta_faq: str, similitud: float):
    """
    Registra en la base de datos la similitud semántica detectada entre una consulta del usuario
    y una de las preguntas frecuentes, junto con su score.
    """
    try:
        print("\n======= 📌 REGISTRO DE SIMILITUD SEMÁNTICA =======")
        print(f"👤 user_id: {user_id}")
        print(f"🗨️ Consulta: {consulta}")
        print(f"❓ Pregunta FAQ: {pregunta_faq}")
        print(f"📏 Score de similitud: {similitud:.4f}")

        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO faq_similitud_logs (user_id, consulta, pregunta_faq, similitud)
            VALUES (%s, %s, %s, %s);
        """, (user_id, consulta, pregunta_faq, float(similitud)))

        conn.commit()
        conn.close()
        print("✅ Similitud registrada correctamente.\n")

    except Exception as e:
        print(f"❌ Error al registrar log de similitud: {e}")

def registrar_auditoria_respuesta(user_id: str, respuesta_original: str, respuesta_final: str, motivo_modificacion: str = None):
    """
    Registra la respuesta original de OpenAI y su versión final (modificada) en una tabla de auditoría.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auditoria_respuestas (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                respuesta_original TEXT NOT NULL,
                respuesta_final TEXT NOT NULL,
                motivo_modificacion TEXT,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)  # Seguridad: autocrea la tabla si no existe

        cursor.execute("""
            INSERT INTO auditoria_respuestas (user_id, respuesta_original, respuesta_final, motivo_modificacion)
            VALUES (%s, %s, %s, %s);
        """, (user_id, respuesta_original.strip(), respuesta_final.strip(), motivo_modificacion))
        conn.commit()
        conn.close()
        print("📑 Auditoría registrada en auditoria_respuestas.")
    except Exception as e:
        print(f"❌ Error al registrar auditoría de respuesta: {e}")

def generar_resumen_clinico_y_estado(session: dict, contador: int) -> str:
    """
    Genera una respuesta clínica con base en emociones detectadas y síntomas coincidentes.
    Se aplica en la interacción 5 y 9, devolviendo síntomas literales y estado emocional predominante.
    """

    mensajes = session.get("mensajes", [])
    emociones_acumuladas = session.get("emociones_detectadas", [])

    # Detectar nuevas emociones
    emociones_detectadas = detectar_emociones_negativas(" ".join(mensajes)) or []

    # ✅ Unificación sin duplicados
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
        if len(coincidencias_sintomas) >= 2 else
        "No se pudo establecer con certeza un estado emocional predominante."
    )

    emociones_literal = ", ".join(emociones_unificadas[:3])

    respuesta = (
        f"Con base a lo que has descripto —{emociones_literal}—, "
        f"pareciera ser que el malestar emocional predominante es: {cuadro_predominante}. "
        f"Te sugiero considerar una consulta con el Lic. Daniel O. Bustamante escribiéndole al WhatsApp +54 911 3310-1186 para una evaluación más detallada."
    )

    print(f"🧾 Resumen clínico generado correctamente en interacción {contador}")
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

@app.post("/asistente")
async def asistente(input_data: UserInput):
    try:
        user_id = input_data.user_id
        mensaje_original = input_data.mensaje.strip()
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
        
        # 🔒 Interacción 10: cierre profesional definitivo
        if contador == 10:
            emocion_inferida = session.get("emocion_inferida_9")
            if emocion_inferida and (
                emocion_inferida in mensaje_usuario or "sí" in mensaje_usuario or "me pasa" in mensaje_usuario
            ):
                if emocion_inferida not in session["emociones_detectadas"]:
                    session["emociones_detectadas"].append(emocion_inferida)
                    registrar_emocion(emocion_inferida, f"confirmación de inferencia (interacción 10)", user_id)
        
            respuesta = (
                "He encontrado interesante nuestra conversación, pero para profundizar más en el análisis de tu malestar, "
                "sería ideal que consultes con un profesional. Por ello, te sugiero que te contactes con el Lic. Bustamante. "
                "Lamentablemente, no puedo continuar con la conversación más allá de este punto."
            )
        
            prediccion = predecir_evento_futuro(session["mensajes"])
            if prediccion != "sin predicción identificada":
                print(f"🔮 Proyección detectada: {prediccion}")
                registrar_inferencia(user_id, contador, "prediccion", prediccion)
                respuesta += f" Por otra parte, se identificó que mencionaste una posible consecuencia o desenlace: {prediccion}."
        
            registrar_respuesta_openai(interaccion_id, respuesta)
            return {"respuesta": respuesta}      

        # ⛔ Interrupción anticipada si ya se detectó input sospechoso
        if session.get("input_sospechoso"):
            return {
                "respuesta": (
                    "Recordá que este espacio está destinado a consultas clínicas. "
                    "Si necesitás ayuda emocional, contámelo con claridad."
                )
            }

        # 🧠 Nueva respuesta para la PRIMERA INTERACCIÓN
        if contador == 1:
            # ⚠️ Reforzar que si es SALUDO + contenido clínico, se trate como clínico
            if tipo_input == SALUDO and es_tema_clinico_o_emocional(mensaje_usuario):
                tipo_input = CLINICO
        
            # ✅ Si es clínico o hay contexto clínico previo, generar respuesta profesional
            if tipo_input in [CLINICO, CLINICO_CONTINUACION] or hay_contexto_clinico_anterior(user_id) or es_tema_clinico_o_emocional(mensaje_usuario):
                prompt = (
                    f"Mensaje recibido del usuario: '{mensaje_usuario}'.\n\n"
                    "Redactá una respuesta breve, profesional y clínica como si fueras el asistente virtual del Lic. Daniel O. Bustamante, psicólogo.\n\n"
                    "Estilo y directrices obligatorias:\n"
                    "- Mantené un tono clínico, sobrio, profesional y respetuoso.\n"
                    "- Comenzá la respuesta con un saludo breve como 'Hola, ¿qué tal?'.\n"
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
       
                respuesta_original = generar_respuesta_con_openai(prompt, contador, user_id, mensaje_usuario, mensaje_original)
        
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
        
        # ✅ En la interacción 5 y 9, generar resumen clínico y estado emocional predominante
        if contador == 5:
            if not session["emociones_detectadas"]:
                nuevas = detectar_emociones_negativas(" ".join(session["mensajes"])) or []
                session["emociones_detectadas"].extend([e for e in nuevas if e not in session["emociones_detectadas"]])
        
            resumen = generar_resumen_clinico_y_estado(session, contador)
        
            # 🧠 Realizar inferencia clínica intuitiva
            try:
                conn = psycopg2.connect(DATABASE_URL)
                emocion_inferida = inferir_emocion_no_dicha(session["emociones_detectadas"], conn)
                conn.close()
            except Exception as e:
                print("❌ Error al conectar a la base para inferencia en interacción 5:", e)
                emocion_inferida = None
        
            # Guardar inferencia en la sesión
            session["emocion_inferida_5"] = emocion_inferida
        
            if emocion_inferida:
                respuesta = (
                    f"{resumen} Además, ¿dirías que también podrías estar atravesando cierta {emocion_inferida}? "
                    f"Lo pregunto porque suele aparecer en casos similares."
                )
            else:
                respuesta = f"{resumen} ¿te interesaría consultarlo con el Lic. Daniel O. Bustamante?"
        
            registrar_respuesta_openai(interaccion_id, respuesta)
            return {"respuesta": respuesta}

        if contador == 6 and session.get("emocion_inferida_5"):
            emocion = session["emocion_inferida_5"]
            if emocion in mensaje_usuario or "sí" in mensaje_usuario or "me pasa" in mensaje_usuario:
                if emocion not in session["emociones_detectadas"]:
                    session["emociones_detectadas"].append(emocion)
                    registrar_emocion(emocion, f"confirmación de inferencia (interacción 6)", user_id)
        
                return {
                    "respuesta": (
                        f"Gracias por confirmarlo. ¿Querés contarme un poco más sobre cómo se manifiesta esa {emocion}?"
                    )
                }

        
        if contador == 9:
            mensajes_previos = session["mensajes"][-3:]
            emociones_nuevas = []
        
            for mensaje in mensajes_previos:
                nuevas = detectar_emociones_negativas(mensaje) or []
                for emocion in nuevas:
                    emocion = emocion.lower().strip()
                    if emocion not in session["emociones_detectadas"]:
                        emociones_nuevas.append(emocion)
        
            # Validar si hay emociones previas, y si no, intentar detectar de nuevo
            if not session["emociones_detectadas"] and emociones_nuevas:
                session["emociones_detectadas"].extend(emociones_nuevas)
            else:
                session["emociones_detectadas"] = list(set(session["emociones_detectadas"] + emociones_nuevas))
        
            # Registrar emociones nuevas no presentes en BD para esta interacción
            emociones_registradas_bd = obtener_emociones_ya_registradas(user_id, contador)
            for emocion in emociones_nuevas:
                if emocion not in emociones_registradas_bd:
                    registrar_emocion(emocion, f"interacción {contador}", user_id)
        
            # 🧠 Estado emocional global sintetizado por cerebro_simulado
            estado_global = clasificar_estado_mental(session["mensajes"])
            if estado_global != "estado emocional no definido":
                print(f"🧠 Estado global sintetizado: {estado_global}")
                registrar_inferencia(user_id, contador, "estado_mental", estado_global)
        
            # 🧾 Generar resumen clínico con todas las emociones acumuladas
            resumen = generar_resumen_clinico_y_estado(session, contador)
        
            # 🧠 Inferencia emocional adicional (segunda intuición clínica)
            try:
                conn = psycopg2.connect(DATABASE_URL)
                emocion_inferida = inferir_emocion_no_dicha(session["emociones_detectadas"], conn)
                conn.close()
            except Exception as e:
                print("❌ Error al conectar a la base para inferencia en interacción 9:", e)
                emocion_inferida = None
        
            session["emocion_inferida_9"] = emocion_inferida
        
            if emocion_inferida:
                respuesta = (
                    f"{resumen} Además, ¿te ha pasado sentir también {emocion_inferida}? "
                    f"Lo menciono porque es un patrón que suele aparecer cuando coexisten estos síntomas."
                )
            else:
                respuesta = (
                    f"{resumen} Además, se identificó un posible estado emocional global: {estado_global}. "
                    f"¿te interesaría consultarlo con el Lic. Daniel O. Bustamante?"
                )
        
            registrar_respuesta_openai(interaccion_id, respuesta)
            return {"respuesta": respuesta}

        if contador >= 11:
            print(f"🔒 Interacción {contador}: se activó el modo de cierre definitivo. No se realizará nuevo análisis clínico.")
        
            # 🧠 Detección de intención de cierre con cerebro_simulado
            cierre_detectado = inferir_intencion_usuario(session["mensajes"])
            print(f"🧠 Intención inferida por el cerebro simulado: {cierre_detectado}")
        
            if cierre_detectado == "intención de cierre":
                registrar_inferencia(user_id, contador, "intencion_de_cierre", cierre_detectado)
                return {
                    "respuesta": (
                        "Gracias por tu mensaje. Me alegra haber podido brindarte orientación en este espacio. "
                        "Si en algún momento deseás avanzar con una consulta, podés escribirle al Lic. Bustamante. "
                        + obtener_mensaje_contacto()
                    )
                }
        
            # Si no hay cierre explícito, usar cierre profesional rotativo según cantidad de emociones
            cantidad_emociones = len(set(session.get("emociones_detectadas", [])))
        
            if cantidad_emociones >= 2:
                respuestas_cierre_definitivo = [
                    "Gracias por compartir lo que estás sintiendo. Ya hemos recorrido juntos un análisis significativo. Para seguir avanzando, te recomiendo contactar al Lic. Bustamante. " + obtener_mensaje_contacto(),
                    "Valoro la confianza con la que expresaste tus emociones. Este espacio ya cumplió su función de orientación. Para una atención personalizada, podés continuar con el Lic. Bustamante. " + obtener_mensaje_contacto(),
                    "Hemos llegado al punto en que una intervención profesional directa sería lo más adecuado. El Lic. Bustamante está disponible para ayudarte. " + obtener_mensaje_contacto(),
                    "Agradezco tu apertura durante esta conversación. Para seguir explorando lo que estás atravesando en profundidad, lo ideal es hacerlo con el Lic. Bustamante en un entorno clínico. " + obtener_mensaje_contacto(),
                    "Lo que compartiste ha sido importante. A partir de aquí, solo un espacio terapéutico puede brindarte el acompañamiento que necesitás. " + obtener_mensaje_contacto()
                ]
            else:
                respuestas_cierre_definitivo = [
                    "Este espacio ha llegado a su límite. Si deseás avanzar con una consulta, podés escribirle al Lic. Bustamante. " + obtener_mensaje_contacto(),
                    "Para continuar, es necesario un espacio clínico adecuado. Podés contactar al Lic. Bustamante si querés seguir con esta consulta. " + obtener_mensaje_contacto(),
                    "Este asistente ha cumplido su función orientativa. Para una atención más profunda, podés escribirle al Lic. Bustamante. " + obtener_mensaje_contacto()
                ]
        
            return {"respuesta": random.choice(respuestas_cierre_definitivo)}

        
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
        
        
        # 🔹 Generar respuesta con OpenAI si no es la interacción 5, 9 o 10+
        prompt = (
            f"Mensaje recibido del usuario: '{mensaje_usuario}'.\n\n"
            "Redactá una respuesta breve, profesional y clínica como si fueras el asistente virtual del Lic. Daniel O. Bustamante, psicólogo.\n\n"
            "Estilo y directrices obligatorias:\n"
            "- Mantené un tono clínico, sobrio, profesional y respetuoso.\n"
            "- Comenzá la respuesta con un saludo breve como 'Hola, ¿qué tal?'.\n"
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

        # Obtener respuesta de OpenAI
        respuesta_original = generar_respuesta_con_openai(prompt, contador, user_id, mensaje_usuario, mensaje_original)

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
