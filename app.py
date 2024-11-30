from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json

# Configuración de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Inicializar Flask
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://licbustamante.com.ar"}})

# Conectar con Google Sheets
def conectar_google_sheets():
    try:
        CREDENCIALES_JSON = os.getenv("GOOGLE_CREDENTIALS_FILE")
        if not CREDENCIALES_JSON:
            raise ValueError("La variable de entorno GOOGLE_CREDENTIALS_FILE no está configurada o está vacía.")

        creds_dict = json.loads(CREDENCIALES_JSON)
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
    try:
        data = request.get_json()
        if not data or "mensaje" not in data:
            return jsonify({"respuesta": "Falta el campo 'mensaje'"}), 400

        mensaje_usuario = data["mensaje"].strip().lower()
        hoja = conectar_google_sheets()
        if not hoja:
            raise ValueError("No se pudo conectar con Google Sheets.")

        # Obtener todos los registros, omitiendo los encabezados
        datos = hoja.get_all_records()
        coincidencias = []

        # Verificar coincidencias en las columnas "A", "B" y "C"
        for fila in datos:
            if mensaje_usuario in [fila.get("A", "").lower(), fila.get("B", "").lower(), fila.get("C", "").lower()]:
                coincidencias.append(fila.get("D", "").strip())

        if len(coincidencias) > 0:
            # Si hay coincidencias, generar una respuesta con OpenAI
            sintomas = ", ".join(set(coincidencias))
            prompt = (
                f"En base a los síntomas mencionados ({mensaje_usuario}) y las coincidencias detectadas ({sintomas}), "
                "genera una respuesta profesional mencionando los síntomas reportados y sugiriendo contacto con el Lic. Daniel O. Bustamante."
            )
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un asistente profesional que responde de manera clara, profesional y empática, sin dramatización ni insistencia."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=150,
            )
            respuesta_openai = response["choices"][0]["message"]["content"].strip()
        else:
            # Si no hay coincidencias, registrar los síntomas en la hoja
            hoja.append_row([mensaje_usuario, "", "", ""])
            respuesta_openai = (
                "No encontré coincidencias claras en mi base de datos. Tus síntomas serán registrados para futuras referencias. "
                "Si lo consideras necesario, contacta al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186."
            )

        return jsonify({"respuesta": respuesta_openai})

    except Exception as e:
        print("Error procesando la solicitud:", e)
        return jsonify({"respuesta": "Lo siento, ocurrió un error procesando tu solicitud."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
