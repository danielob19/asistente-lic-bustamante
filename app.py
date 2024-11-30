from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random
import json

# Configuración de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Inicializar Flask
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://licbustamante.com.ar"}})

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

        data = hoja.get_all_records()
        coincidencias = []
        for fila in data:
            if any(sintoma.lower() in [fila["A"].lower(), fila["B"].lower(), fila["C"].lower()] for sintoma in sintomas_usuario):
                coincidencias.append(fila["D"])
        return coincidencias
    except Exception as e:
        print(f"Error cotejando síntomas: {e}")
        return None

# Registrar síntomas en Google Sheets
def registrar_sintomas_google_sheets(sintomas_usuario):
    try:
        hoja = conectar_google_sheets()
        if hoja:
            for sintoma in sintomas_usuario:
                hoja.append_row([sintoma, "Sinónimo pendiente", "Sinónimo pendiente", "Diagnóstico pendiente"])
    except Exception as e:
        print(f"Error registrando en Google Sheets: {e}")

# Ruta principal
@app.route("/", methods=["GET"])
def home():
    return jsonify({"mensaje": "¡Bienvenido al Asistente Lic. Bustamante!"})

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
        respuestas_pregunta = [
            "¿Podrías contarme si hay algún otro malestar que sientas?",
            "¿Hay algo más que te preocupe emocionalmente?",
            "¿Aparte de esto, sentís algún otro síntoma?"
        ]

        if coincidencias and len(set(coincidencias)) >= 2:
            posibles_diagnosticos = ", ".join(set(coincidencias))
            prompt = (
                f"Con base en los síntomas mencionados: {', '.join(sintomas_usuario)}. "
                f"Estos coinciden con los siguientes diagnósticos: {posibles_diagnosticos}. "
                f"Responde profesionalmente y sugiere contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 para más orientación."
            )
        else:
            registrar_sintomas_google_sheets(sintomas_usuario)
            prompt = (
                f"No se encontraron coincidencias claras para los síntomas mencionados: {', '.join(sintomas_usuario)}. "
                f"Indica que estos serán registrados y sugiere contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 para orientación especializada."
            )

        # Generar respuesta con OpenAI
        try:
            respuesta_openai = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un asistente profesional que responde de manera clara, breve y profesional."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=150
            )["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"Error con OpenAI: {e}")
            respuesta_openai = "Lo siento, ocurrió un error procesando tu solicitud."

        # Respuesta final con preguntas adicionales
        if "¿podrías contarme" in prompt.lower():
            respuesta_final = respuesta_openai
        else:
            respuesta_final = respuesta_openai + " " + random.choice(respuestas_pregunta)

        return jsonify({"respuesta": respuesta_final})
    except Exception as e:
        print(f"Error procesando la solicitud: {e}")
        return jsonify({"error": "Lo siento, ocurrió un error procesando tu solicitud."}), 500

# Ejecutar la aplicación
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
