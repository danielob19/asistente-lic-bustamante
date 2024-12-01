from flask import Flask, request, jsonify, session
from flask_cors import CORS
import openai
import os

# Configuración de Flask
app = Flask(__name__)
CORS(app, supports_credentials=True)
app.secret_key = "supersecretkey"  # Necesario para manejar sesiones

# Configuración de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")  # Asegúrate de configurar esta variable de entorno

# Ruta principal del asistente
@app.route("/asistente", methods=["POST"])
def asistente():
    try:
        # Inicializar sesión si es necesario
        if "estado_conversacion" not in session:
            session["estado_conversacion"] = "inicio"
        if "nombre_usuario" not in session:
            session["nombre_usuario"] = None
        if "respuestas_usuario" not in session:
            session["respuestas_usuario"] = []

        # Obtener el mensaje del usuario
        data = request.get_json()
        mensaje_usuario = data.get("mensaje", "").strip()

        if not mensaje_usuario:
            return jsonify({"respuesta": "Por favor, proporcioná un mensaje válido."}), 400

        estado = session["estado_conversacion"]
        nombre = session["nombre_usuario"]
        respuestas = session["respuestas_usuario"]

        # Gestionar la conversación
        if estado == "inicio":
            # Saludo inicial y solicitud del nombre
            respuesta = generar_respuesta_openai("Saluda al usuario cortésmente y pídele su nombre.")
            session["estado_conversacion"] = "nombre"
            return jsonify({"respuesta": respuesta})

        elif estado == "nombre":
            # Guardar el nombre del usuario y saludarlo nuevamente
            session["nombre_usuario"] = mensaje_usuario
            nombre = mensaje_usuario
            respuesta = generar_respuesta_openai(
                f"Saluda cortésmente a {nombre} y preséntate como el Asistente del Lic. Daniel O. Bustamante."
            )
            session["estado_conversacion"] = "consulta1"
            return jsonify({"respuesta": respuesta})

        elif estado == "consulta1":
            # Preguntar sobre lo que motiva la consulta
            respuesta = generar_respuesta_openai(
                "Pregúntale al usuario en un lenguaje enriquecido qué lo está afectando y qué motiva su consulta."
            )
            session["estado_conversacion"] = "consulta2"
            respuestas.append(mensaje_usuario)
            session["respuestas_usuario"] = respuestas
            return jsonify({"respuesta": respuesta})

        elif estado == "consulta2":
            # Preguntar nuevamente con una variación
            respuesta = generar_respuesta_openai(
                "Pregúntale al usuario qué otro malestar le afecta, utilizando una variación en la formulación."
            )
            session["estado_conversacion"] = "recomendacion"
            respuestas.append(mensaje_usuario)
            session["respuestas_usuario"] = respuestas
            return jsonify({"respuesta": respuesta})

        elif estado == "recomendacion":
            # Recomendar contacto con el Lic. Daniel O. Bustamante
            descripcion = " ".join(respuestas + [mensaje_usuario])
            respuesta = generar_respuesta_openai(
                f"En base a la descripción del usuario: '{descripcion}', "
                "recomienda cortésmente que solicite un turno con el Lic. Daniel O. Bustamante al whatsapp +54 911 3310-1186 "
                "para evaluar en detalle su malestar."
            )
            session.clear()  # Limpiar sesión tras finalizar la conversación
            return jsonify({"respuesta": respuesta})

    except Exception as e:
        return jsonify({"error": str(e), "respuesta": "Ocurrió un error interno en el servidor."}), 500


# Generador de respuestas usando GPT-3.5 Turbo
def generar_respuesta_openai(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Usamos GPT-3.5 Turbo
            messages=[
                {"role": "system", "content": "Eres un asistente conversacional cortés y profesional."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.7
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"Error generando respuesta con OpenAI: {e}")
        return "Lo siento, ocurrió un error generando la respuesta."

# Iniciar el servidor Flask
if __name__ == "__main__":
    app.run(debug=True)
