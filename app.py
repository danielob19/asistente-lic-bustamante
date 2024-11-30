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

        # Obtener registros y encabezados
        registros = hoja.get_all_records()
        encabezados = registros[0].keys()

        columnas_esperadas = ['Celda A1: "A"', 'Celda B1: "B"', 'Celda C1: "C"', 'Celda D1: "D"']
        if not all(col in encabezados for col in columnas_esperadas):
            raise KeyError(f"Encabezados de la hoja no coinciden con {columnas_esperadas}.")

        coincidencias = []
        for fila in registros:
            for sintoma in sintomas_usuario:
                if (
                    sintoma.lower() in str(fila['Celda A1: "A"']).lower()
                    or sintoma.lower() in str(fila['Celda B1: "B"']).lower()
                    or sintoma.lower() in str(fila['Celda C1: "C"']).lower()
                ):
                    coincidencias.append(fila['Celda D1: "D"'])
        return coincidencias
    except Exception as e:
        print(f"Error cotejando síntomas: {e}")
        return None

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

        if coincidencias and len(set(coincidencias)) >= 2:
            posibles_diagnosticos = ", ".join(set(coincidencias))
            respuesta = (
                f"En base a los síntomas que mencionaste: {', '.join(sintomas_usuario)}, podría haber una coincidencia con los siguientes cuadros: {posibles_diagnosticos}. "
                f"Te sugiero contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 para recibir una evaluación más detallada."
            )
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
