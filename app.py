from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from io import StringIO

# Configuración de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Inicialización de Flask
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://licbustamante.com.ar"}})

# Conexión a Google Sheets
def conectar_google_sheets():
    try:
        # Ruta o credenciales desde variable de entorno
        creds_json = os.getenv("GOOGLE_CREDENTIALS_FILE")
        if not creds_json:
            raise ValueError("GOOGLE_CREDENTIALS_FILE no configurada en variables de entorno.")
        
        creds_dict = json.loads(creds_json)
        creds_stream = StringIO(json.dumps(creds_dict))
        
        # Configuración de alcance
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_stream, scope)
        client = gspread.authorize(creds)

        # Conectar con la hoja de cálculo
        hoja = client.open("Asistente_Lic_Bustamante").worksheet("tab2")
        return hoja
    except Exception as e:
        print(f"Error al conectar con Google Sheets: {e}")
        return None

# Función para cotejar síntomas
def cotejar_sintomas_google_sheets(sintomas_usuario):
    try:
        hoja = conectar_google_sheets()
        if not hoja:
            return None

        # Leer datos de las columnas A, B, C y D
        data = hoja.get_all_records()

        coincidencias = []
        for fila in data:
            if any(sintoma.lower() in (fila["Celda A1: \"A\""].lower(), fila["Celda B1: \"B\""].lower(), fila["Celda C1: \"C\""].lower()) for sintoma in sintomas_usuario):
                coincidencias.append(fila["Celda D1: \"D\""])
        
        return coincidencias
    except Exception as e:
        print(f"Error cotejando síntomas: {e}")
        return None

# Ruta principal
@app.route("/", methods=["GET"])
def home():
    return jsonify({"mensaje": "¡Bienvenido al Asistente Lic. Bustamante!"})

@app.route("/asistente", methods=["POST"])
def asistente():
    try:
        data = request.get_json()
        if not data or "mensaje" not in data:
            return jsonify({"error": "Falta el campo 'mensaje'"}), 400
        
        mensaje_usuario = data["mensaje"]

        # Procesar síntomas
        sintomas_usuario = [s.strip() for s in mensaje_usuario.split(",")]
        coincidencias = cotejar_sintomas_google_sheets(sintomas_usuario)

        # Generar respuesta con OpenAI
        if coincidencias:
            posibles_diagnosticos = ", ".join(set(coincidencias))
            prompt = (
                f"Con base en los síntomas reportados: {', '.join(sintomas_usuario)}. "
                f"Se encontraron coincidencias con los posibles diagnósticos: {posibles_diagnosticos}. "
                f"Responde profesionalmente, sugiriendo al usuario contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 para más ayuda."
            )
        else:
            prompt = (
                f"No se encontraron coincidencias claras para los síntomas reportados: {', '.join(sintomas_usuario)}. "
                f"Informa al usuario que sus síntomas serán registrados y sugiere contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 para más ayuda."
            )

        try:
            respuesta_openai = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un asistente profesional que responde de forma clara, breve y profesional."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=150
            )["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"Error con OpenAI: {e}")
            respuesta_openai = "Lo siento, ocurrió un error procesando tu solicitud."

        # Registrar datos en Google Sheets
        try:
            hoja = conectar_google_sheets()
            if hoja:
                hoja.append_row([mensaje_usuario, respuesta_openai, "Sinónimo pendiente", "Diagnóstico pendiente"])
        except Exception as e:
            print(f"Error registrando en Google Sheets: {e}")

        return jsonify({"respuesta": respuesta_openai})

    except Exception as e:
        print(f"Error procesando la solicitud: {e}")
        return jsonify({"error": "Lo siento, ocurrió un error procesando tu solicitud."}), 500

# Ejecutar la aplicación
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
