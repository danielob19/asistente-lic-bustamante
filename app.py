from flask import Flask, request, jsonify, session
from flask_cors import CORS
import openai
import os

# Configuración de Flask
app = Flask(__name__)
CORS(app, supports_credentials=True)
app.secret_key = "supersecretkey"  # Necesario para manejar sesiones

# Configuración de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")  # Configura esta variable de entorno

# Ruta principal para interactuar con OpenAI
@app.route("/asistente", methods=["POST"])
def asistente():
    try:
        # Verificar y depurar la sesión
        if "contador_interacciones" not in session:
            print("Inicializando contador de interacciones en la sesión.")
            session["contador_interacciones"] = 0  # Contador de interacciones
        if "respuestas_usuario" not in session:
            print("Inicializando respuestas de usuario en la sesión.")
            session["respuestas_usuario"] = []  # Respuestas acumuladas del usuario

        # Leer el mensaje del usuario
        data = request.get_json()
        mensaje_usuario = data.get("mensaje", "").strip()

        if not mensaje_usuario:
            return jsonify({"error": "Por favor, proporciona un mensaje válido."}), 400

        # Incrementar el contador de interacciones
        session["contador_interacciones"] += 1
        session["respuestas_usuario"].append(mensaje_usuario)

        # Depuración: Imprimir el estado actual de la sesión
        print(f"Estado actual de la sesión: {dict(session)}")

        # Verificar si es la segunda interacción
        if session["contador_interacciones"] >= 2:
            respuesta_final = (
                "Gracias por compartir cómo te sientes. "
                "Para una evaluación más profunda de tu malestar, te recomiendo solicitar un turno de consulta con el Lic. Daniel O. Bustamante "
                "al WhatsApp +54 911 3310-1186, siempre que sea de tu interés resolver tu afección psicológica y emocional."
            )
            session.clear()  # Limpiar la sesión al final del flujo
            return jsonify({"respuesta": respuesta_final})

        # Enviar solicitud a OpenAI para generar una respuesta
        respuesta = interactuar_con_openai(mensaje_usuario)
        return jsonify({"respuesta": respuesta})

    except Exception as e:
        print(f"Error procesando la solicitud: {e}")
        return jsonify({"error": str(e), "mensaje": "Error al procesar la solicitud."}), 500


# Función para interactuar con OpenAI
def interactuar_con_openai(mensaje_usuario):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Cambia a "gpt-4" si prefieres ese modelo
            messages=[
                {"role": "system", "content": "Eres un asistente conversacional que responde de manera profesional."},
                {"role": "user", "content": mensaje_usuario}
            ],
            max_tokens=200,
            temperature=0.7
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"Error interactuando con OpenAI: {e}")
        return "Lo siento, ocurrió un problema al generar la respuesta."


# Iniciar el servidor Flask
if __name__ == "__main__":
    app.run(debug=True)
