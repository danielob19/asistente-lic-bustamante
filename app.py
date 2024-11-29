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

# Saludos iniciales
saludos = [
    "¡Hola! ¿En qué puedo ayudarte hoy?",
    "¡Buen día! ¿Cómo puedo asistirte?",
    "Hola, gracias por comunicarte. ¿En qué puedo ayudarte?"
]

# Preguntas iterativas
preguntas_iterativas = [
    "¿Podrías contarme si hay algún otro síntoma que te preocupe?",
    "¿Aparte de esto, sentís algún otro malestar?",
    "Entiendo. ¿Te afecta algún otro síntoma?"
]

# Respuestas finales
respuestas_finales = [
    "Gracias por tu tiempo. Si necesitas ayuda adicional, no dudes en volver. Recordá que podés contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186.",
    "Espero haberte sido de ayuda. Si lo considerás oportuno, podés contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186.",
    "Entendido. Si necesitás más apoyo, no dudes en comunicarte nuevamente. Podés hablar con el Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186."
]

# Respuestas para agradecimientos
respuestas_agradecimiento = [
    "Gracias a vos por comunicarte. Si necesitás más ayuda, estoy aquí.",
    "De nada, espero haberte ayudado. Que tengas un buen día.",
    "Gracias a vos. Si en algún momento necesitás más orientación, no dudes en volver."
]

# Frases para detectar fin de conversación
respuestas_fin_usuario = [
    "ningún otro síntoma",
    "no tengo más síntomas",
    "no",
    "eso es todo",
    "ya te dije"
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

        # Detectar saludo inicial
        if mensaje_usuario in ["hola", "buen día", "buenas tardes", "buenas noches"]:
            return jsonify({"respuesta": random.choice(saludos)})

        # Detectar agradecimientos
        if mensaje_usuario in ["gracias", "muchas gracias"]:
            return jsonify({"respuesta": random.choice(respuestas_agradecimiento)})

        # Detectar fin de conversación
        if mensaje_usuario in respuestas_fin_usuario:
            return jsonify({"respuesta": random.choice(respuestas_finales)})

        # Conexión a Google Sheets
        hoja = conectar_google_sheets()
        if not hoja:
            raise ValueError("No se pudo conectar con Google Sheets.")

        # Registro y procesamiento en Google Sheets
        hoja.append_row([mensaje_usuario, "", "", ""])
        logging.debug("Nuevo síntoma registrado en Google Sheets.")

        # Preguntar sobre más síntomas
        return jsonify({"respuesta": random.choice(preguntas_iterativas)})

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
