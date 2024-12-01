import os
import json
import random
from flask import Flask, request, jsonify
from flask_cors import CORS
import openai

# Configuración de Flask
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://licbustamante.com.ar"}})

# Configuración de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Base de conocimiento local
base_de_conocimiento = {
    "angustia": "cuadro de angustia",
    "nervioso": "nerviosismo",
    "ansiedad": "cuadro de ansiedad",
    "cansancio": "depresión",
    "atonito": "estrés",
    # Agrega más términos según sea necesario...
}

# Archivo para almacenar síntomas pendientes
archivo_sintomas_pendientes = "sintomas_pendientes.json"

# Función para cargar síntomas pendientes
def cargar_sintomas_pendientes():
    if os.path.exists(archivo_sintomas_pendientes):
        with open(archivo_sintomas_pendientes, "r") as f:
            return json.load(f)
    return []

# Función para guardar nuevos síntomas en el archivo local
def registrar_sintomas_pendientes(sintomas):
    sintomas_pendientes = cargar_sintomas_pendientes()
    sintomas_pendientes.append(sintomas)
    with open(archivo_sintomas_pendientes, "w") as f:
        json.dump(sintomas_pendientes, f, indent=4)
    print(f"Síntomas pendientes registrados: {sintomas}")

# Función para interpretar los síntomas usando OpenAI
def interpretar_sintomas(sintomas):
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

# Función para manejar la conversación
def manejar_conversacion(mensaje_usuario, sintomas_recibidos):
    """Gestiona la conversación fluida con el usuario, incluyendo saludos."""
    respuestas_generales = [
        "¿Podrías contarme si hay algún otro síntoma que te preocupe?",
        "¿Hay algo más que quieras mencionar sobre cómo te sentís?",
        "¿Aparte de eso, qué otro malestar sentís?",
        "Entendido. ¿Podés decirme si tenés algún otro síntoma?"
    ]

    # Saludo inicial si no hay síntomas registrados
    if not sintomas_recibidos:
        return "¡Hola! ¿En qué puedo ayudarte hoy?"

    # Finalizar la conversación si el usuario dice "no" o similar
    if mensaje_usuario.lower() in ["no", "nada más", "listo", "terminé"]:
        if sintomas_recibidos:
            diagnosticos = [
                base_de_conocimiento[sintoma]
                for sintoma in sintomas_recibidos
                if sintoma in base_de_conocimiento
            ]
            if diagnosticos:
                respuesta_final = (
                    f"En base a los síntomas que mencionaste ({', '.join(sintomas_recibidos)}), "
                    f"podrías estar atravesando un estado relacionado con {', '.join(set(diagnosticos))}. "
                    "Si lo considerás necesario, contactá al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 "
                    "para una evaluación más profunda. Gracias por compartir cómo te sentís."
                )
            else:
                respuesta_final = (
                    "Gracias por compartir cómo te sentís. Si considerás necesario, contactá al Lic. Daniel O. Bustamante "
                    "al WhatsApp +54 911 3310-1186 para una consulta más detallada."
                )
        else:
            respuesta_final = (
                "Gracias por compartir cómo te sentís. Si considerás necesario, contactá al Lic. Daniel O. Bustamante "
                "al WhatsApp +54 911 3310-1186 para una consulta más detallada."
            )
        return respuesta_final

    # Evitar repetir preguntas por síntomas ya registrados
    if mensaje_usuario in sintomas_recibidos:
        return "Ya mencionaste ese síntoma. ¿Podrías contarme si hay algún otro síntoma que te preocupe?"

    # Agregar síntoma y continuar
    sintomas_recibidos.append(mensaje_usuario)

    # Finalizar automáticamente si hay más de 3 síntomas
    if len(sintomas_recibidos) >= 3:
        diagnosticos = [
            base_de_conocimiento[sintoma]
            for sintoma in sintomas_recibidos
            if sintoma in base_de_conocimiento
        ]
        if diagnosticos:
            respuesta_final = (
                f"En base a los síntomas que mencionaste ({', '.join(sintomas_recibidos)}), "
                f"podrías estar atravesando un estado relacionado con {', '.join(set(diagnosticos))}. "
                "Si lo considerás necesario, contactá al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 "
                "para una evaluación más profunda. Gracias por compartir cómo te sentís."
            )
        else:
            respuesta_final = (
                "Gracias por compartir cómo te sentís. Si considerás necesario, contactá al Lic. Daniel O. Bustamante "
                "al WhatsApp +54 911 3310-1186 para una consulta más detallada."
            )
        return respuesta_final

    # Continuar la conversación con preguntas variadas
    return random.choice(respuestas_generales)

# Ruta principal del asistente
@app.route("/asistente", methods=["POST"])
def asistente():
    try:
        data = request.get_json()
        mensaje_usuario = data.get("mensaje", "").strip().lower()
        sintomas_recibidos = data.get("sintomas", [])

        if not mensaje_usuario:
            return jsonify({"respuesta": "Por favor, proporcioná un mensaje válido."})

        respuesta = manejar_conversacion(mensaje_usuario, sintomas_recibidos)

        return jsonify({"respuesta": respuesta, "sintomas": sintomas_recibidos})

    except Exception as e:
        print(f"Error procesando la solicitud: {e}")
        return jsonify({"respuesta": "Lo siento, ocurrió un error procesando tu solicitud."})

# Iniciar la aplicación
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
