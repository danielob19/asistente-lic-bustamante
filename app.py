from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json

# Configuración de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Inicializa la aplicación Flask
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

def conectar_google_sheets():
    """Conecta a Google Sheets y devuelve la hoja activa."""
    try:
        # Ruta al archivo secreto en Render
        CREDENCIALES_JSON_PATH = "/etc/secrets/GOOGLE_CREDENTIALS_FILE"

        # Verifica que el archivo exista
        if not os.path.exists(CREDENCIALES_JSON_PATH):
            raise FileNotFoundError(f"No se encontró el archivo de credenciales en {CREDENCIALES_JSON_PATH}")

        # Configuración de alcance y autenticación
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENCIALES_JSON_PATH, scope)

        # Conexión al cliente de Google Sheets
        client = gspread.authorize(creds)
        hoja = client.open("Asistente_Lic_Bustamante").worksheet("tab2")
        return hoja
    except Exception as e:
        print("Error al conectar con Google Sheets:", e)
        return None

@app.route("/", methods=["GET"])
def home():
    """Ruta principal de prueba."""
    return jsonify({"mensaje": "¡Bienvenido al Asistente Lic. Bustamante!"})

@app.route("/asistente", methods=["POST"])
def asistente():
    """Procesa mensajes del usuario y genera una respuesta."""
    data = request.get_json()
    if not data or "mensaje" not in data:
        return jsonify({"error": "Falta el campo 'mensaje'"}), 400

    mensaje_usuario = data["mensaje"]
    hoja = conectar_google_sheets()

    try:
        # Preguntar tres veces con variación en la introducción
        preguntas = [
            "¿Hola, en qué te puedo ayudar hoy?",
            "¿Qué malestar emocional o psicológico sientes hoy?",
            "¿Puedo asistirte con algo relacionado a tu bienestar emocional?"
        ]
        
        if "etapa" not in data:
            return jsonify({"pregunta": preguntas[0]}), 200

        etapa = data["etapa"]
        if etapa == 1:
            return jsonify({"pregunta": preguntas[1]}), 200
        elif etapa == 2:
            return jsonify({"pregunta": preguntas[2]}), 200

        # Verificar coincidencias en Google Sheets
        sintomas_usuario = mensaje_usuario.lower().split()
        coincidencias = []
        if hoja:
            sintomas_tabla = hoja.get_all_records()
            for fila in sintomas_tabla:
                sintomas_columna = [fila["A"], fila["B"], fila["C"]]
                if any(sintoma.lower() in sintomas_usuario for sintoma in sintomas_columna):
                    coincidencias.append(fila["D"])

        if len(set(coincidencias)) >= 2:
            # Enviar a OpenAI para enriquecer la respuesta
            enfermedad = coincidencias[0]
            prompt = f"El usuario tiene los síntomas: {', '.join(sintomas_usuario)}. Con base en mi conocimiento, parece que tiene {enfermedad}. Responde de manera profesional en menos de 70 palabras, sugiriendo contacto con el Lic. Daniel O. Bustamante al whatsapp +54 911 3310-1186 para una evaluación más profunda."
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un asistente profesional psicológico."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=150
            )
            respuesta_openai = response['choices'][0]['message']['content'].strip()
        else:
            # Si no hay coincidencias, agregar síntomas nuevos a la hoja
            if hoja:
                hoja.append_row([mensaje_usuario, "", "", ""])
            respuesta_openai = (
                "No encontré información específica para tus síntomas, pero los he registrado para revisión. "
                "Si lo consideras oportuno, puedes contactar al Lic. Daniel O. Bustamante al whatsapp +54 911 3310-1186."
            )
    except Exception as e:
        print("Error procesando la solicitud:", e)
        respuesta_openai = "Lo siento, no puedo procesar tu solicitud en este momento."

    return jsonify({"respuesta": respuesta_openai})

@app.route('/favicon.ico')
def favicon():
    """Manejar solicitudes de favicon.ico."""
    return '', 204  # Devuelve una respuesta vacía sin contenido

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
