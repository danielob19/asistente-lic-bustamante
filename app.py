from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import os

# Configuración de Flask
app = Flask(__name__)
CORS(app, supports_credentials=True)

# Configuración de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")  # Configura esta variable de entorno

# Ruta principal para interactuar con OpenAI
@app.route("/asistente", methods=["POST"])
def asistente():
    try:
        # Leer el mensaje del usuario
        data = request.get_json()
        mensaje_usuario = data.get("mensaje", "").strip()

        if not mensaje_usuario:
            return jsonify({"error": "Por favor, proporciona un mensaje válido."}), 400

        # Enviar solicitud a OpenAI
        respuesta = interactuar_con_openai(mensaje_usuario)

        return jsonify({"respuesta": respuesta})
    except Exception as e:
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
