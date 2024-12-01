from flask import Flask, request, jsonify, session
from flask_cors import CORS
import os
import random

# Configuración de Flask
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://licbustamante.com.ar"}})
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecretkey")  # Necesario para sesiones

# Base de conocimiento local
base_de_conocimiento = {
    "angustia": "cuadro de angustia",
    "nervioso": "nerviosismo",
    "ansiedad": "cuadro de ansiedad",
    "cansancio": "depresión",
    "atonito": "estrés",
    # Agrega más términos según sea necesario...
}

# Lista de palabras inapropiadas
palabras_inapropiadas = ["puto", "idiota", "tonto", "imbécil"]

# Función para filtrar lenguaje inapropiado
def filtrar_lenguaje_inapropiado(mensaje):
    if any(palabra in mensaje for palabra in palabras_inapropiadas):
        return "Por favor, mantengamos el respeto en esta conversación."
    return None

# Función para manejar la conversación
def manejar_conversacion(mensaje_usuario, sintomas_recibidos):
    respuestas_generales = [
        "¿Podrías contarme si hay algún otro síntoma que te preocupe?",
        "¿Hay algo más que quieras mencionar sobre cómo te sentís?",
        "¿Aparte de eso, qué otro malestar sentís?",
        "Entendido. ¿Podés decirme si tenés algún otro síntoma?"
    ]

    # Saludo inicial si no hay síntomas registrados
    if not sintomas_recibidos:
        return "¡Hola! ¿En qué puedo ayudarte hoy?"

    # Evitar repetir preguntas por síntomas ya registrados
    if mensaje_usuario in sintomas_recibidos:
        return "Ya mencionaste ese síntoma. ¿Podrías contarme si hay algún otro síntoma que te preocupe?"

    # Agregar síntoma y continuar
    sintomas_recibidos.append(mensaje_usuario)

    # Finalizar automáticamente si hay más de 3 síntomas
    if len(sintomas_recibidos) >= 3:
        diagnosticos = [
            base_de_conocimiento.get(sintoma, "desconocido")
            for sintoma in sintomas_recibidos
        ]
        diagnosticos = [diag for diag in diagnosticos if diag != "desconocido"]

        if diagnosticos:
            return (
                f"En base a los síntomas que mencionaste ({', '.join(sintomas_recibidos)}), "
                f"podrías estar atravesando un estado relacionado con {', '.join(set(diagnosticos))}. "
                "Si lo considerás necesario, contactá al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 "
                "para una evaluación más profunda. Gracias por compartir cómo te sentís."
            )
        else:
            return (
                "Gracias por compartir cómo te sentís. Si considerás necesario, contactá al Lic. Daniel O. Bustamante "
                "al WhatsApp +54 911 3310-1186 para una consulta más detallada."
            )

    # Continuar la conversación con preguntas variadas
    return random.choice(respuestas_generales)

# Ruta principal del asistente
@app.route("/asistente", methods=["POST"])
def asistente():
    try:
        data = request.get_json()
        mensaje_usuario = data.get("mensaje", "").strip().lower()

        # Recuperar la lista de síntomas de la sesión
        sintomas_recibidos = session.get("sintomas_recibidos", [])

        if not mensaje_usuario:
            return jsonify({"respuesta": "Por favor, proporcioná un mensaje válido."})

        # Verificar lenguaje inapropiado
        filtro = filtrar_lenguaje_inapropiado(mensaje_usuario)
        if filtro:
            return jsonify({"respuesta": filtro, "sintomas": sintomas_recibidos})

        # Manejar la conversación
        respuesta = manejar_conversacion(mensaje_usuario, sintomas_recibidos)

        # Guardar la lista actualizada de síntomas en la sesión
        session["sintomas_recibidos"] = sintomas_recibidos

        return jsonify({"respuesta": respuesta, "sintomas": sintomas_recibidos})

    except Exception as e:
        print(f"Error procesando la solicitud: {e}")
        return jsonify({"respuesta": "Lo siento, ocurrió un error procesando tu solicitud."})

# Iniciar la aplicación
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
