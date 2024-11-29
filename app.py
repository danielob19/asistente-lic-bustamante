from flask import Flask, request, jsonify
import openai
import gspread
import os
import json
from oauth2client.service_account import ServiceAccountCredentials
import logging

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

        mensaje_usuario = data["mensaje"]
        logging.debug(f"Mensaje recibido: {mensaje_usuario}")

        # Consulta con OpenAI
        try:
            respuesta_openai = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un asistente profesional que responde en un encuadre psicológico existencial. Respondes de forma profesional, sin dramatización ni insistencia. Tu respuesta debe estar limitada a 70 palabras y sugerir contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 si el usuario lo considera oportuno."},
                    {"role": "user", "content": mensaje_usuario}
                ],
                temperature=0.7,
                max_tokens=150
            )
            respuesta_texto = respuesta_openai["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logging.error(f"Error al conectar con OpenAI: {e}")
            respuesta_texto = "Lo siento, no pude procesar tu solicitud en este momento."

        # Registrar en Google Sheets
        try:
            hoja = conectar_google_sheets()
            if hoja:
                hoja.append_row([mensaje_usuario, respuesta_texto, "pendiente", "pendiente"])
                logging.debug("Datos registrados en Google Sheets.")
            else:
                logging.error("No se pudo registrar en Google Sheets: conexión no establecida.")
        except Exception as e:
            logging.error(f"Error al registrar en Google Sheets: {e}")

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
