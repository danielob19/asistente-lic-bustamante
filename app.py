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
    "¡Hola! ¿Cómo estás? ¿En qué puedo ayudarte?",
    "¡Hola! Gracias por comunicarte. Contame, ¿en qué te puedo asistir?",
    "Hola, espero que estés bien. ¿Qué te trae por aquí hoy?"
]

# Preguntas iterativas
preguntas_iterativas = [
    "¿Aparte de esto, sentís algún otro malestar?",
    "¿Te afecta algo más emocionalmente?",
    "Entiendo. ¿Podrías contarme si hay algo más que te preocupe?"
]

# Respuestas finales
respuestas_finales = [
    "Gracias por compartir. Si necesitás más ayuda, no dudes en volver. Recordá que podés contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186.",
    "Espero haberte sido útil. Si lo considerás oportuno, podés hablar con el Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186.",
    "Gracias por tu tiempo. Si necesitás orientación adicional, estoy aquí para ayudarte. Además, podés contactar al Lic. Daniel O. Bustamante para una consulta más profunda."
]

# Respuestas para agradecimientos
respuestas_agradecimiento = [
    "De nada, espero haberte ayudado. Que tengas un buen día.",
    "Gracias a vos por confiar. Si necesitás algo más, no dudes en volver.",
    "De nada. Recordá que siempre podés contar conmigo para cualquier consulta."
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
        CREDENCIALES_JSON_CONTENT = os.getenv("GOOGLE_CREDENTIALS_FILE")
        if not CREDENCIALES_JSON_CONTENT:
            raise ValueError("No se encontró ninguna credencial de Google configurada.")

        creds_dict = json.loads(CREDENCIALES_JSON_CONTENT)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

        # Conexión con Google Sheets
        client = gspread.authorize(creds)
        hoja = client.open("Asistente_Lic_Bustamante").worksheet("tab2")
        logging.debug("Conexión exitosa con Google Sheets.")
        return hoja
    except Exception as e:
        logging.error(f"Error al conectar con Google Sheets: {e}")
        return None


def cotejar_sintomas(mensaje_usuario, hoja):
    """Coteja los síntomas del usuario con Google Sheets."""
    try:
        registros = hoja.get_all_records()
        coincidencias = [registro for registro in registros if mensaje_usuario in registro.values()]
        if coincidencias:
            # Encontrar el posible diagnóstico (columna "D")
            diagnosticos = list(set([c["D"] for c in coincidencias]))
            return diagnosticos
        return []
    except Exception as e:
        logging.error(f"Error al cotejar síntomas: {e}")
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

        hoja = conectar_google_sheets()
        if not hoja:
            raise ValueError("No se pudo conectar con Google Sheets.")

        # Detectar saludo inicial
        if mensaje_usuario in ["hola", "buen día", "buenas tardes", "buenas noches"]:
            return jsonify({"respuesta": random.choice(saludos)})

        # Detectar agradecimientos
        if mensaje_usuario in ["gracias", "muchas gracias"]:
            return jsonify({"respuesta": random.choice(respuestas_agradecimiento)})

        # Detectar fin de conversación
        if mensaje_usuario in respuestas_fin_usuario:
            return jsonify({"respuesta": random.choice(respuestas_finales)})

        # Cotejar síntomas
        diagnosticos = cotejar_sintomas(mensaje_usuario, hoja)

        if diagnosticos:
            # Usar OpenAI para enriquecer la respuesta
            sintomas_mencionados = mensaje_usuario
            prompt = f"El usuario menciona los síntomas '{sintomas_mencionados}'. Según los datos, podría tratarse de: {', '.join(diagnosticos)}. Genera una respuesta profesional, empática y breve para sugerir una consulta psicológica, mencionando los síntomas proporcionados por el usuario."
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=150
            )
            respuesta = response['choices'][0]['message']['content']
            return jsonify({"respuesta": respuesta})

        # Registrar nuevos síntomas si no hay coincidencias
        hoja.append_row([mensaje_usuario, "", "", ""])
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
