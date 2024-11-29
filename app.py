from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import logging
import json
from io import StringIO

# Configuración de logs
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuración de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    logging.error("La variable de entorno OPENAI_API_KEY no está configurada.")

# Configuración de Flask
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://licbustamante.com.ar"}})

# Función para conectar con Google Sheets
def conectar_google_sheets():
    """Conecta a Google Sheets y devuelve la hoja activa."""
    try:
        # Obtener las credenciales de Google desde las variables de entorno
        CREDENCIALES_JSON = os.getenv("GOOGLE_CREDENTIALS_FILE")
        if not CREDENCIALES_JSON:
            raise ValueError("La variable de entorno GOOGLE_CREDENTIALS_FILE no está configurada.")
        
        # Cargar las credenciales en un diccionario
        creds_dict = json.loads(CREDENCIALES_JSON)
        creds_stream = StringIO(json.dumps(creds_dict))

        # Configuración de alcance y autenticación
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_stream, scope)

        # Conectar con Google Sheets
        client = gspread.authorize(creds)
        hoja = client.open("Asistente_Lic_Bustamante").worksheet("tab2")
        logging.debug("Conexión exitosa con Google Sheets.")
        return hoja
    except Exception as e:
        logging.error(f"Error al conectar con Google Sheets: {e}")
        return None

@app.route("/", methods=["GET"])
def home():
    """Ruta principal de prueba."""
    return jsonify({"mensaje": "¡Bienvenido al Asistente Lic. Bustamante!"})

@app.route("/asistente", methods=["POST"])
def asistente():
    """Ruta para interactuar con el asistente."""
    try:
        data = request.get_json()
        logging.debug(f"Datos recibidos: {data}")

        if not data or "mensaje" not in data:
            return jsonify({"error": "Falta el campo 'mensaje'"}), 400

        mensaje_usuario = data["mensaje"]

        # Lógica del asistente
        hoja = conectar_google_sheets()
        sintomas_encontrados = []

        if hoja:
            registros = hoja.get_all_records()
            for registro in registros:
                if mensaje_usuario.lower() in map(str.lower, [registro["A"], registro["B"], registro["C"]]):
                    sintomas_encontrados.append(registro["D"])

        if len(sintomas_encontrados) >= 2:
            enfermedad_probable = sintomas_encontrados[0]
            prompt_openai = f"El usuario menciona los síntomas: {mensaje_usuario}. Esto podría estar relacionado con: {enfermedad_probable}. Genera una respuesta profesional y breve, sugiriendo al usuario que contacte al Lic. Daniel O. Bustamante."
        else:
            hoja.append_row([mensaje_usuario, "", "", ""])
            prompt_openai = f"El usuario menciona un síntoma nuevo: {mensaje_usuario}. Por favor, responde de forma profesional sugiriendo al usuario que contacte al Lic. Daniel O. Bustamante para una evaluación más profunda."

        # Llamada a OpenAI
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres un asistente profesional psicológico especializado. Responde en estilo profesional y breve, max. 70 palabras."},
                {"role": "user", "content": prompt_openai}
            ],
            temperature=0.7,
            max_tokens=150
        )

        respuesta_openai = response['choices'][0]['message']['content'].strip()
        logging.debug(f"Respuesta de OpenAI: {respuesta_openai}")

        return jsonify({"respuesta": respuesta_openai})

    except Exception as e:
        logging.error(f"Error procesando la solicitud: {e}")
        return jsonify({"respuesta": "Lo siento, no pude procesar tu solicitud en este momento."}), 500

@app.route('/favicon.ico')
def favicon():
    """Manejar solicitudes de favicon.ico."""
    return '', 204

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
