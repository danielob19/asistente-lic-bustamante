import os
import psycopg2
import openai
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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

# Función genérica para interactuar con OpenAI
def interactuar_con_openai(prompt, max_tokens=150, temperature=0.3):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        print(f"Error al interactuar con OpenAI: {e}")
        return "Error al procesar la solicitud."

# Detectar emociones negativas o patrones de conducta negativos
def detectar_emociones_negativas(mensaje):
    prompt = (
        f"Analiza el siguiente mensaje y detecta exclusivamente emociones humanas negativas o patrones de conducta negativos. "
        f"Devuelve una lista separada por comas con las emociones detectadas. Si no hay emociones negativas, responde 'ninguna'.\n\n"
        f"Mensaje: {mensaje}"
    )
    try:
        response = interactuar_con_openai(prompt, max_tokens=50, temperature=0.0)
        emociones = response.split(",")
        return [emocion.strip().lower() for emocion in emociones if emocion.strip().lower() != "ninguna"]
    except Exception as e:
        print(f"Error al detectar emociones negativas: {e}")
        return []

# Registrar emociones negativas detectadas en la base de datos
def registrar_emocion_negativa(emocion, contexto):
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO emociones_detectadas (emocion, contexto) 
                    VALUES (%s, %s);
                    """,
                    (emocion.strip().lower(), contexto.strip())
                )
                conn.commit()
        print(f"Emoción negativa '{emocion}' registrada exitosamente con contexto: {contexto}.")
    except Exception as e:
        print(f"Error al registrar emoción: {e}")

# Inicializar la base de datos
def init_db():
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS emociones_detectadas (
                        id SERIAL PRIMARY KEY,
                        emocion TEXT NOT NULL,
                        contexto TEXT NOT NULL,
                        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
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
        print("Base de datos inicializada correctamente.")
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")

# Registrar un síntoma detectado
def registrar_sintoma(sintoma, cuadro):
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO palabras_clave (sintoma, cuadro) 
                    VALUES (%s, %s)
                    ON CONFLICT (sintoma) DO UPDATE SET cuadro = EXCLUDED.cuadro;
                    """,
                    (sintoma.strip().lower(), cuadro.strip().lower())
                )
                conn.commit()
        print(f"Síntoma '{sintoma}' registrado exitosamente con cuadro: {cuadro}.")
    except Exception as e:
        print(f"Error al registrar síntoma: {e}")

# Obtener síntomas existentes de la base de datos
def obtener_sintomas():
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT sintoma, cuadro FROM palabras_clave;")
                return cursor.fetchall()
    except Exception as e:
        print(f"Error al obtener síntomas: {e}")
        return []

# Clase para solicitudes del usuario
class UserInput(BaseModel):
    mensaje: str
    user_id: str

# Endpoint principal del asistente
@app.post("/asistente")
async def asistente(input_data: UserInput):
    mensaje_usuario = input_data.mensaje.strip()
    user_id = input_data.user_id

    if not mensaje_usuario:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

    emociones_detectadas = detectar_emociones_negativas(mensaje_usuario)
    for emocion in emociones_detectadas:
        registrar_emocion_negativa(emocion, mensaje_usuario)

    if emociones_detectadas:
        return {
            "respuesta": (
                f"Detecté las siguientes emociones negativas: {', '.join(emociones_detectadas)}. "
                f"¿Podrías contarme más sobre cómo te sientes o qué situaciones las generan?"
            )
        }
    else:
        return {"respuesta": "No detecté emociones negativas en tu mensaje. ¿Hay algo más en lo que pueda ayudarte?"}

# Lógica para manejar interacciones específicas
def manejar_interaccion_personalizada(contador, emociones_detectadas):
    if contador == 5:
        return (
            f"En base a las emociones negativas detectadas ({', '.join(emociones_detectadas)}), parece que podríamos estar frente a un cuadro "
            f"relacionado con algunos de los síntomas. Te recomiendo consultar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 para "
            f"obtener ayuda profesional detallada."
        )
    elif contador in [6, 7, 8]:
        preguntas = {
            6: "¿Qué crees que podría estar causando estas emociones en este momento?",
            7: "¿En qué situaciones específicas sientes estas emociones con mayor intensidad?",
            8: "¿Cómo afectan estas emociones a tus actividades diarias o relaciones con otras personas?",
        }
        return preguntas.get(contador, "¿Podrías contarme más sobre cómo te sientes?")
    elif contador == 9:
        return (
            f"A partir de las emociones negativas identificadas anteriormente ({', '.join(emociones_detectadas)}), y tras analizar la situación, "
            f"sería recomendable profundizar en estos sentimientos con un profesional. No olvides que puedes contactar al Lic. Daniel O. Bustamante "
            f"al WhatsApp +54 911 3310-1186 para más información."
        )
    elif contador == 10:
        return (
            "Si bien es muy interesante nuestra charla, debo concluirla aquí. Te invito a que consultes al Lic. Daniel O. Bustamante para una "
            "evaluación más profunda de lo que te está afectando. Puedes escribirle al WhatsApp +54 911 3310-1186 para obtener ayuda profesional."
        )
    else:
        return "Estoy aquí para seguir conversando si lo necesitas. Cuéntame más sobre lo que sientes."

# Manejo de interacciones con contador
@app.post("/interaccion")
async def manejar_interaccion(input_data: UserInput):
    user_id = input_data.user_id
    mensaje_usuario = input_data.mensaje.strip()

    # Aquí podrías implementar un sistema de sesiones o almacenamiento temporal de datos por usuario
    # Por simplicidad, este ejemplo es estático
    contador = 1  # Simula el contador de interacciones, incrementarlo según lógica
    emociones_detectadas = detectar_emociones_negativas(mensaje_usuario)
    respuesta = manejar_interaccion_personalizada(contador, emociones_detectadas)

    return {"respuesta": respuesta}

