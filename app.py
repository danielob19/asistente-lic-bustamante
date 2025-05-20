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
from core.utils_seguridad import es_input_malicioso
from core.faq_semantica import generar_embeddings_faq, buscar_respuesta_semantica_con_score


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

from core.config.palabras_irrelevantes import palabras_irrelevantes
from core.modelos import UserInput


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


    # ✅ Sugerencia de contacto solo en interacciones 5, 9 y 10
    if contador in [5, 9, 10]:
        respuesta += (
            " ¿Te interesaría consultarlo con el Lic. Daniel O. Bustamante? "
            "Podés escribirle al WhatsApp +54 911 3310-1186 para una evaluación más detallada."
        )

    print(f"📋 Resumen clínico generado correctamente en interacción {contador}")
    session["mensajes"].clear()
    return respuesta


