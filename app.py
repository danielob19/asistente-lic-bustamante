from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# Configuración de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Inicializar Flask
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Conexión a Google Sheets
def conectar_google_sheets():
    try:
        creds_json = os.getenv("GOOGLE_CREDENTIALS_FILE")
        if not creds_json:
            raise ValueError("GOOGLE_CREDENTIALS_FILE no configurada en las variables de entorno.")
        creds_dict = json.loads(creds_json)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        hoja = client.open("Asistente_Lic_Bustamante").worksheet("tab2")
        return hoja
    except Exception as e:
        print(f"Error al conectar con Google Sheets: {e}")
        return None

# Cotejar síntomas en Google Sheets
def cotejar_sintomas_google_sheets(sintomas_usuario):
    try:
        hoja = conectar_google_sheets()
        if not hoja:
            return None

        registros = hoja.get_all_records()
        coincidencias = []

        for fila in registros:
            for sintoma in sintomas_usuario:
                if (
                    sintoma.lower() in str(fila.get('Celda A1: "A"', '')).lower()
                    or sintoma.lower() in str(fila.get('Celda B1: "B"', '')).lower()
                    or sintoma.lower() in str(fila.get('Celda C1: "C"', '')).lower()
                ):
                    coincidencias.append(fila.get('Celda D1: "D"', 'Diagnóstico pendiente'))

        return coincidencias
    except Exception as e:
        print(f"Error cotejando síntomas: {e}")
        return None

# Generar respuesta con OpenAI
def generar_respuesta_openai(sintomas_usuario, diagnosticos):
    try:
        prompt = (
            f"El usuario mencionó los siguientes síntomas: {', '.join(sintomas_usuario)}. "
            f"Coincidencias encontradas: {', '.join(diagnosticos)}. "
            "Redacta una respuesta profesional de no más de 70 palabras, sugiriendo al usuario contactar al Lic. Daniel O. Bustamante para una evaluación más profunda. "
            "Evita dramatizar y enfócate en un tono profesional y objetivo."
        )
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": "Eres un asistente profesional de psicología."},
                      {"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.7
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"Error generando respuesta con OpenAI: {e}")
        return "Lamentablemente, no puedo proporcionar una respuesta en este momento. Por favor, intenta más tarde."

# Ruta del asistente
@app.route("/asistente", methods=["POST"])
def asistente():
    try:
        data = request.get_json()
        if not data or "mensaje" not in data:
            return jsonify({"error": "Falta el campo 'mensaje'"}), 400

        mensaje_usuario = data["mensaje"].lower()
        sintomas_usuario = [sintoma.strip() for sintoma in mensaje_usuario.split(",")]

        coincidencias = cotejar_sintomas_google_sheets(sintomas_usuario)
        if coincidencias and len(coincidencias) >= 2:
            respuesta = generar_respuesta_openai(sintomas_usuario, coincidencias)
        else:
            respuesta = (
                f"No encontré coincidencias claras para los síntomas mencionados: {', '.join(sintomas_usuario)}. "
                f"Tus síntomas serán registrados y puedes contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 para orientación adicional."
            )

        return jsonify({"respuesta": respuesta})
    except Exception as e:
        print(f"Error procesando la solicitud: {e}")
        return jsonify({"error": "Ocurrió un error procesando tu solicitud."}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
