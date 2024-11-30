from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json

# Configuración de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")  # Configurada como variable de entorno

# Inicializar Flask
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://licbustamante.com.ar"}})  # Permite solicitudes desde tu dominio

# Conectar con Google Sheets
def conectar_google_sheets():
    try:
        # Obtener credenciales de Google desde una variable de entorno
        CREDENCIALES_JSON = os.getenv("GOOGLE_CREDENTIALS_FILE")
        if not CREDENCIALES_JSON:
            raise ValueError("La variable de entorno GOOGLE_CREDENTIALS_FILE no está configurada o está vacía.")

        # Configurar conexión a Google Sheets
        creds_dict = json.loads(CREDENCIALES_JSON)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)

        # Abrir la hoja y devolver la pestaña activa
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
        # Obtener datos del usuario
        data = request.get_json()
        if not data or "mensaje" not in data:
            return jsonify({"respuesta": "Falta el campo 'mensaje'"}), 400

        mensaje_usuario = data["mensaje"].strip().lower()

        # Conexión con Google Sheets
        hoja = conectar_google_sheets()
        if not hoja:
            raise ValueError("No se pudo conectar con Google Sheets.")

        # Leer datos de la hoja
        datos = hoja.get_all_records()
        coincidencias = []

        # Buscar coincidencias en las columnas A, B, C
        for fila in datos:
            if not all(col in fila for col in ["A", "B", "C", "D"]):
                continue
            if mensaje_usuario in [fila["A"].lower(), fila["B"].lower(), fila["C"].lower()]:
                coincidencias.append(fila["D"])

        # Generar respuesta
        if len(coincidencias) > 1:
            sintomas = ", ".join(set(coincidencias))
            prompt = f"En base a los síntomas {sintomas}, genera una respuesta profesional que mencione los síntomas y sugiera contacto con el Lic. Daniel O. Bustamante."
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un asistente profesional que responde en un encuadre psicológico existencial, evitando dramatización y dando respuestas profesionales."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=150,
            )
            respuesta_openai = response["choices"][0]["message"]["content"].strip()
        elif len(coincidencias) == 1:
            respuesta_openai = f"Parece que tus síntomas están relacionados con {coincidencias[0]}. Si lo consideras oportuno, te recomiendo contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186."
        else:
            respuesta_openai = "No encontré coincidencias claras en mi base de datos. Tus síntomas serán registrados para futuras referencias. Si lo consideras necesario, contacta al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186."

        # Registrar datos del usuario en la hoja
        hoja.append_row([mensaje_usuario, "", "", respuesta_openai])

        return jsonify({"respuesta": respuesta_openai})

    except Exception as e:
        print("Error procesando la solicitud:", e)
        return jsonify({"respuesta": "Lo siento, ocurrió un error procesando tu solicitud."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
