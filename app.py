from flask import Flask, request, jsonify
from flask_cors import CORS  # Para manejar CORS
import openai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
from io import StringIO

# Configuración de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")  # Configurada como variable de entorno

# Función para conectar con Google Sheets
def conectar_google_sheets():
    """Conecta a Google Sheets y devuelve la hoja activa."""
    try:
        # Obtén el contenido del archivo secreto desde la variable de entorno
        CREDENCIALES_JSON = os.getenv("GOOGLE_CREDENTIALS_FILE")
        if not CREDENCIALES_JSON:
            raise ValueError("La variable de entorno GOOGLE_CREDENTIALS_FILE no está configurada o está vacía.")

        # Convierte el contenido del archivo JSON a un diccionario
        creds_dict = json.loads(CREDENCIALES_JSON)

        # Configuración de alcance y autenticación
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

        # Autenticación y conexión
        client = gspread.authorize(creds)
        hoja = client.open("Asistente_Lic_Bustamante").worksheet("tab2")
        return hoja
    except Exception as e:
        print("Error al conectar con Google Sheets:", e)
        return None

# Inicializar Flask y configurar CORS
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Permite solicitudes desde cualquier origen

@app.route("/", methods=["GET"])
def home():
    """Ruta principal de prueba."""
    return jsonify({"mensaje": "¡Bienvenido al Asistente Lic. Bustamante!"})

@app.route("/asistente", methods=["POST"])
def asistente():
    """Ruta principal para interactuar con el asistente."""
    data = request.get_json()
    if not data or "mensaje" not in data:
        return jsonify({"error": "Falta el campo 'mensaje'"}), 400

    mensaje_usuario = data["mensaje"]

    # Generar respuesta con OpenAI
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres un asistente profesional que responde en un encuadre psicológico existencial. Respondes de forma profesional, sin dramatización ni insistencia. Tu respuesta debe estar limitada a 70 palabras y sugerir únicamente contactar al Lic. Daniel O. Bustamante si al usuario le parece oportuno."},
                {"role": "user", "content": mensaje_usuario}
            ],
            temperature=0.7,
            max_tokens=150
        )
        respuesta_openai = response['choices'][0]['message']['content'].strip()
    except Exception as e:
        print("Error al conectar con OpenAI:", e)
        respuesta_openai = "Lo siento, no puedo procesar tu solicitud en este momento."

    # Registrar mensaje en Google Sheets
    try:
        hoja = conectar_google_sheets()
        if hoja:
            hoja.append_row([mensaje_usuario, respuesta_openai])
    except Exception as e:
        print("Error al registrar en Google Sheets:", e)

    return jsonify({"respuesta": respuesta_openai})

@app.route('/favicon.ico')
def favicon():
    """Manejar solicitudes de favicon.ico."""
    return '', 204  # Devuelve una respuesta vacía sin contenido

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
