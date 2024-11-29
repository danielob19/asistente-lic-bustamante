from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import random
import json
from io import StringIO

# Configuración de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Configuración de la aplicación Flask y CORS
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Conexión a Google Sheets
def conectar_google_sheets():
    """Conecta a Google Sheets y devuelve la hoja activa."""
    try:
        CREDENCIALES_JSON = os.getenv("GOOGLE_CREDENTIALS_FILE")
        if not CREDENCIALES_JSON:
            raise ValueError("La variable de entorno GOOGLE_CREDENTIALS_FILE no está configurada.")

        creds_dict = json.loads(CREDENCIALES_JSON)
        creds_stream = StringIO(json.dumps(creds_dict))

        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

        client = gspread.authorize(creds)
        hoja = client.open("Asistente_Lic_Bustamante").worksheet("tab2")
        return hoja
    except Exception as e:
        print("Error al conectar con Google Sheets:", e)
        return None

# Frases aleatorias para el Asistente
frases_iniciales = [
    "Hola, ¿en qué te puedo ayudar hoy?",
    "¡Bienvenido! ¿Qué necesitas compartir conmigo?",
    "¿Cómo te sientes hoy? Estoy aquí para ayudarte."
]

frases_seguimiento = [
    "¿Aparte de tu estado actual, qué otro malestar sentís?",
    "Entendido. ¿Hay algo más que te preocupe?",
    "Comprendido. ¿Podrías contarme si sentís otro malestar?"
]

frases_adicionales = [
    "¿Sentís algún otro malestar anímico?",
    "¿Hay algún síntoma adicional que quieras mencionar?",
    "¿Algo más que te gustaría agregar sobre cómo te sentís?"
]

# Función para generar respuesta enriquecida con OpenAI
def generar_respuesta_openai(sintomas):
    prompt = f"En base a los síntomas que me referís: {', '.join(sintomas)}, pareciera ser que estarías atravesando un estado de estrés anímico. " \
             f"Te sugiero, en caso de considerarlo oportuno, solicitar un turno de consulta con el Lic. Daniel O. Bustamante al whatsapp +54 911 3310-1186 " \
             f"para una evaluación más profunda de tu malestar. Responde en un máximo de 70 palabras, en lenguaje profesional, sin dramatizar ni aconsejar actividades físicas o respiratorias."
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=150
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        print("Error al generar respuesta con OpenAI:", e)
        return "Lo siento, no puedo procesar tu solicitud en este momento."

# Ruta principal
@app.route("/asistente", methods=["POST"])
def asistente():
    """Interacción con el Asistente."""
    data = request.get_json()
    if not data or "mensaje" not in data:
        return jsonify({"error": "Falta el campo 'mensaje'"}), 400

    mensaje_usuario = data["mensaje"].strip()
    hoja = conectar_google_sheets()
    sintomas_usuario = [mensaje_usuario]
    if not hoja:
        return jsonify({"error": "No se pudo conectar con Google Sheets"}), 500

    try:
        # Cotejar síntomas con Google Sheets
        registros = hoja.get_all_records()
        coincidencias = []
        for registro in registros:
            for columna in ["A", "B", "C"]:
                if mensaje_usuario.lower() in str(registro[columna]).lower():
                    coincidencias.append(registro["D"])
        
        if len(coincidencias) >= 2:
            # Generar respuesta enriquecida si hay suficientes coincidencias
            respuesta = generar_respuesta_openai(list(set(coincidencias)))
        else:
            # Registrar síntomas nuevos en Google Sheets si no hay suficientes coincidencias
            hoja.append_row([mensaje_usuario, "", "", ""])
            respuesta = f"Gracias por compartir esta información. He registrado tus síntomas para análisis. Te sugiero, si lo considerás oportuno, contactar al Lic. Daniel O. Bustamante al whatsapp +54 911 3310-1186."

        return jsonify({"respuesta": respuesta})
    except Exception as e:
        print("Error al procesar síntomas:", e)
        return jsonify({"error": "Hubo un problema al procesar tu solicitud"}), 500

@app.route("/", methods=["GET"])
def home():
    """Ruta principal de prueba."""
    saludo = random.choice(frases_iniciales)
    return jsonify({"mensaje": saludo})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
