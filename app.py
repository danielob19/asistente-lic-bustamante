from flask import Flask, request, jsonify
import openai
import gspread
import os
import json
from oauth2client.service_account import ServiceAccountCredentials
import logging
import random

# Configuración de logging
logging.basicConfig(level=logging.DEBUG)

# Configuración de la clave API de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("La variable de entorno OPENAI_API_KEY no está configurada o está vacía.")

app = Flask(__name__)

# Permitir solicitudes desde el dominio del cliente
from flask_cors import CORS
CORS(app, resources={r"/*": {"origins": "*"}})

# Preguntas iterativas
preguntas_iterativas = [
    "¿Aparte de tu estado de nerviosismo, qué otro malestar sentís?",
    "Entiendo. ¿Sentís algún otro malestar anímico?",
    "¿Podrías contarme si hay algún otro síntoma que te preocupe?"
]

# Respuestas para finalizar la conversación
respuestas_finales = [
    "Gracias por compartir cómo te sentís. Espero haberte ayudado. Si lo considerás oportuno, podés contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 para una consulta más detallada.",
    "Entendido. Si necesitas más ayuda en otro momento, no dudes en volver. Recordá que podés contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 para explorar tus malestares de forma más profunda.",
    "Gracias por tu tiempo. Si lo necesitás, podés comunicarte con el Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 para una consulta."
]

# Frases para detectar fin de conversación
respuestas_fin_usuario = [
    "ningún otro síntoma",
    "no tengo más síntomas",
    "ya te dije",
    "eso es todo",
    "no"
]


def conectar_google_sheets():
    """Conecta a Google Sheets y devuelve la hoja activa."""
    try:
        # Obtener credenciales de Google desde la variable de entorno o archivo secreto
        CREDENCIALES_JSON_PATH = "/etc/secrets/google-credentials.json"
        CREDENCIALES_JSON_CONTENT = os.getenv("GOOGLE_CREDENTIALS_FILE")

        if os.path.exists(CREDENCIALES_JSON_PATH):
            logging.debug("Usando archivo de credenciales en la ruta especificada.")
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENCIALES_JSON_PATH, scope)
        elif CREDENCIALES_JSON_CONTENT:
            logging.debug("Usando credenciales directamente desde la variable de entorno.")
            creds_dict = json.loads(CREDENCIALES_JSON_CONTENT)
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            raise ValueError("No se encontró ninguna credencial de Google configurada.")

        # Conexión con Google Sheets
        client = gspread.authorize(creds)
        hoja = client.open("Asistente_Lic_Bustamante").worksheet("tab2")
        logging.debug("Conexión exitosa con Google Sheets.")
        return hoja
    except Exception as e:
        logging.error(f"Error al conectar con Google Sheets: {e}")
        return None


def cotejar_respuestas(hoja, sintomas_usuario):
    """Coteja los síntomas del usuario con las columnas de Google Sheets."""
    try:
        filas = hoja.get_all_values()
        coincidencias = []

        for fila in filas[1:]:  # Omitir encabezados
            if any(sintoma in fila[:3] for sintoma in sintomas_usuario):  # Columnas A, B, C
                coincidencias.append(fila[3])  # Enfermedad (columna D)

        return coincidencias
    except Exception as e:
        logging.error(f"Error al cotejar respuestas: {e}")
        return []


@app.route("/", methods=["GET"])
def home():
    """Ruta de prueba."""
    return jsonify({"mensaje": "¡Bienvenido al Asistente Lic. Bustamante!"})


@app.route("/asistente", methods=["POST"])
def asistente():
    """Procesa las solicitudes del usuario."""
    try:
        data = request.get_json()
        if not data or "mensaje" not in data:
            return jsonify({"error": "Falta el campo 'mensaje'"}), 400

        mensaje_usuario = data["mensaje"].strip().lower()
        logging.debug(f"Mensaje recibido: {mensaje_usuario}")

        # Si el usuario indica que no tiene más síntomas, finalizar la conversación
        if mensaje_usuario in respuestas_fin_usuario:
            respuesta_texto = random.choice(respuestas_finales)
            return jsonify({"respuesta": respuesta_texto})

        # Conexión a Google Sheets
        hoja = conectar_google_sheets()
        if not hoja:
            raise ValueError("No se pudo conectar con Google Sheets.")

        # Lógica iterativa de preguntas y cotejo
        sintomas_usuario = [mensaje_usuario]
        coincidencias = cotejar_respuestas(hoja, sintomas_usuario)

        if len(coincidencias) >= 2:
            # Si hay 2 o más coincidencias, generar respuesta enriquecida con OpenAI
            enfermedad = coincidencias[0]  # Tomar la primera coincidencia
            try:
                respuesta_openai = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Eres un asistente profesional que responde en un encuadre psicológico existencial. Respondes de forma profesional, sin dramatización ni insistencia. Tu respuesta debe estar limitada a 70 palabras y sugerir contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 si el usuario lo considera oportuno."},
                        {"role": "user", "content": f"Teniendo en cuenta los síntomas {', '.join(sintomas_usuario)}, ¿qué opinas?"}
                    ],
                    temperature=0.7,
                    max_tokens=150
                )
                respuesta_texto = respuesta_openai["choices"][0]["message"]["content"].strip()
            except Exception as e:
                logging.error(f"Error al conectar con OpenAI: {e}")
                respuesta_texto = "Lo siento, no pude procesar tu solicitud en este momento."
        else:
            # Si no hay suficientes coincidencias, registrar el síntoma y responder
            try:
                hoja.append_row([mensaje_usuario, "", "", ""])
                logging.debug("Nuevo síntoma registrado en Google Sheets.")
            except Exception as e:
                logging.error(f"Error al registrar en Google Sheets: {e}")

            respuesta_texto = random.choice(preguntas_iterativas)

        # Responder al cliente
        return jsonify({"respuesta": respuesta_texto})

    except Exception as e:
        logging.error(f"Error procesando la solicitud: {e}")
        return jsonify({"error": "Ocurrió un error procesando tu solicitud. Por favor, intenta nuevamente."}), 500


@app.route("/favicon.ico")
def favicon():
    """Ignorar solicitudes de favicon."""
    return '', 204


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
