import os
import json
import random
from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
from base_de_conocimiento import base_de_conocimiento
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Configuración de Flask
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://licbustamante.com.ar"}})

# Configuración de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Configuración de Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials_json = os.getenv("GOOGLE_CREDENTIALS_FILE")

if not credentials_json:
    raise ValueError("La variable de entorno GOOGLE_CREDENTIALS_FILE no está configurada.")

credentials = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(credentials_json), scope)
client = gspread.authorize(credentials)

spreadsheet_id = "1cAy1BEENCGHBKxTHBhNTtYjI9WokkW97"
worksheet_name = "sintomas_pendientes"


# Función para interpretar los síntomas usando OpenAI
def interpretar_sintomas(sintomas):
    """Interpreta síntomas y genera respuestas con OpenAI."""
    mensajes = [
        {"role": "system", "content": "Eres un asistente psicológico profesional."},
        {"role": "user", "content": f"El usuario menciona los siguientes síntomas: {sintomas}."}
    ]
    try:
        respuesta_openai = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=mensajes,
            max_tokens=70,
            temperature=0.7
        )
        return respuesta_openai.choices[0].message['content'].strip()
    except openai.error.OpenAIError as e:
        print(f"Error al conectar con OpenAI: {e}")
        return "Lo siento, no pude procesar tu solicitud en este momento."


# Función para registrar síntomas no encontrados
def registrar_sintomas_pendientes(sintomas):
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(worksheet_name)
        worksheet.append_row([sintomas])
        print(f"Síntomas registrados como pendientes: {sintomas}")
    except Exception as e:
        print(f"Error al registrar síntomas pendientes: {e}")


# Función para manejar la conversación
def manejar_conversacion(mensaje_usuario, sintomas_recibidos):
    """Gestiona la conversación fluida con el usuario."""
    respuestas_generales = [
        "¿Podrías contarme si hay algún otro síntoma que te preocupe?",
        "¿Hay algo más que quieras mencionar sobre cómo te sentís?",
        "¿Aparte de eso, qué otro malestar sentís?",
        "Entendido. ¿Podés decirme si tenés algún otro síntoma?"
    ]

    if mensaje_usuario.lower() in ["no", "nada más", "listo", "terminé"]:
        # Si el usuario dice "no" o similar, finalizar la conversación
        diagnosticos = []
        for sintoma in sintomas_recibidos:
            if sintoma in base_de_conocimiento:
                diagnosticos.append(base_de_conocimiento[sintoma])
        if len(set(diagnosticos)) > 0:
            mensaje_diagnostico = (
                f"En base a los síntomas que mencionaste ({', '.join(sintomas_recibidos)}), "
                f"podrías estar atravesando un estado relacionado con {', '.join(set(diagnosticos))}. "
                "Si lo considerás necesario, contactá al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 "
                "para una evaluación más profunda."
            )
        else:
            mensaje_diagnostico = (
                "Gracias por compartir cómo te sentís. Si considerás necesario, contactá al Lic. Daniel O. Bustamante "
                "al WhatsApp +54 911 3310-1186 para una consulta más detallada."
            )
        return mensaje_diagnostico

    elif mensaje_usuario.lower() in ["sí", "si"]:
        # Si el usuario dice "sí", preguntar por más síntomas
        return "Entendido, por favor contame qué otro síntoma sentís."

    else:
        # Agregar síntoma a la lista y continuar la conversación
        sintomas_recibidos.append(mensaje_usuario)
        if mensaje_usuario not in base_de_conocimiento:
            registrar_sintomas_pendientes(mensaje_usuario)

        return random.choice(respuestas_generales)


# Ruta principal del asistente
@app.route("/asistente", methods=["POST"])
def asistente():
    try:
        data = request.get_json()
        mensaje_usuario = data.get("mensaje", "").strip().lower()

        if not mensaje_usuario:
            return jsonify({"respuesta": "Por favor, proporcioná un mensaje válido."})

        # Cargar la conversación actual
        sintomas_recibidos = data.get("sintomas", [])

        # Manejar la conversación
        respuesta = manejar_conversacion(mensaje_usuario, sintomas_recibidos)

        return jsonify({"respuesta": respuesta, "sintomas": sintomas_recibidos})

    except Exception as e:
        print(f"Error procesando la solicitud: {e}")
        return jsonify({"respuesta": "Lo siento, ocurrió un error procesando tu solicitud."})


# Iniciar la aplicación
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
