from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
from io import StringIO

# Configuración de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Inicializar la aplicación Flask y configurar CORS
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://licbustamante.com.ar"}})

# Conexión a Google Sheets
def conectar_google_sheets():
    try:
        # Cargar credenciales desde la variable de entorno
        credenciales_json = os.getenv("GOOGLE_CREDENTIALS_FILE")
        if not credenciales_json:
            raise ValueError("La variable de entorno GOOGLE_CREDENTIALS_FILE no está configurada.")

        creds_dict = json.loads(credenciales_json)
        creds_stream = StringIO(json.dumps(creds_dict))
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        hoja = client.open("Asistente_Lic_Bustamante").worksheet("tab2")
        return hoja
    except Exception as e:
        print("Error al conectar con Google Sheets:", e)
        return None

@app.route("/", methods=["GET"])
def home():
    return jsonify({"mensaje": "¡Bienvenido al Asistente Lic. Bustamante!"})

@app.route("/asistente", methods=["POST"])
def asistente():
    data = request.get_json()
    if not data or "mensaje" not in data:
        return jsonify({"error": "Falta el campo 'mensaje'"}), 400

    mensaje_usuario = data["mensaje"]
    hoja = conectar_google_sheets()

    if not hoja:
        return jsonify({"respuesta": "Lo siento, no puedo conectar con la base de datos en este momento."})

    try:
        # Registrar mensaje del usuario
        hoja.append_row([mensaje_usuario, "", "", ""])

        # Leer Google Sheets para buscar coincidencias
        datos = hoja.get_all_records()
        coincidencias = []
        for fila in datos:
            if mensaje_usuario.lower() in [fila["A"].lower(), fila["B"].lower(), fila["C"].lower()]:
                coincidencias.append(fila["D"])

        # Si hay más de una coincidencia, enviar a OpenAI
        if len(coincidencias) > 1:
            sintomas = ", ".join(set(coincidencias))
            prompt = f"En base a los síntomas {sintomas}, ¿podrías generar un diagnóstico breve y profesional?"
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un asistente profesional que responde de forma profesional y psicológica."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=150
            )
            respuesta_openai = response['choices'][0]['message']['content'].strip()
        else:
            respuesta_openai = "No encontré suficientes coincidencias en mi base de datos, pero puedo registrar tus síntomas para análisis futuros."

        # Registrar respuesta generada
        hoja.append_row(["", respuesta_openai, "", ""])
        return jsonify({"respuesta": respuesta_openai})
    except Exception as e:
        print("Error procesando la solicitud:", e)
        return jsonify({"respuesta": "Lo siento, ocurrió un error procesando tu solicitud."})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
