from flask import Flask, request, jsonify
import openai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random
import os
import json

# Configuración de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Configuración de Google Sheets
def conectar_google_sheets():
    try:
        CREDENCIALES_JSON = os.getenv("GOOGLE_CREDENTIALS_FILE")
        if not CREDENCIALES_JSON:
            raise ValueError("Credenciales de Google Sheets no configuradas.")

        creds_dict = json.loads(CREDENCIALES_JSON)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        hoja = client.open("Asistente_Lic_Bustamante").worksheet("tab2")
        return hoja
    except Exception as e:
        print("Error al conectar con Google Sheets:", e)
        return None

# Inicializar Flask
app = Flask(__name__)

@app.route("/asistente", methods=["POST"])
def asistente():
    data = request.get_json()
    if not data or "mensaje" not in data:
        return jsonify({"respuesta": "Por favor, envía un mensaje válido."})

    mensaje_usuario = data["mensaje"].lower()
    hoja = conectar_google_sheets()
    preguntas_varias = [
        "¿Te afecta algo más emocionalmente?",
        "¿Aparte de esto, sentís algún otro malestar?",
        "¿Hay algo más que te preocupe?",
    ]

    try:
        if mensaje_usuario in ["hola", "buenos días", "buenas tardes", "buenas noches"]:
            return jsonify({"respuesta": random.choice(["Hola, espero que estés bien. ¿Qué te trae por aquí hoy?"])})

        if mensaje_usuario in ["gracias", "muchas gracias"]:
            return jsonify({"respuesta": "Gracias a vos. Si necesitás ayuda en otro momento, estoy acá para ayudarte. Recordá que podés contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186."})

        # Cotejar con Google Sheets
        if hoja:
            datos = hoja.get_all_records()
            coincidencias = []
            for fila in datos:
                if mensaje_usuario in [fila["A"].lower(), fila["B"].lower(), fila["C"].lower()]:
                    coincidencias.append(fila)

            if len(coincidencias) >= 2:
                diagnostico = coincidencias[0]["D"]
                sintomas = ", ".join([fila["A"] for fila in coincidencias])
                respuesta_openai = f"En base a los síntomas que mencionaste ({sintomas}), parece que podrías estar enfrentando {diagnostico}. Si lo considerás oportuno, contactá al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 para una evaluación más profunda."
                return jsonify({"respuesta": respuesta_openai})

            # Registrar nuevos síntomas si no hay coincidencias
            hoja.append_row([mensaje_usuario, "", "", ""])

        # Preguntar aleatoriamente
        pregunta = random.choice(preguntas_varias)
        return jsonify({"respuesta": pregunta})

    except Exception as e:
        print("Error procesando la solicitud:", e)
        return jsonify({"respuesta": "Lo siento, no pude procesar tu solicitud en este momento."})

# Ejecutar servidor
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
