from flask import Flask, request, jsonify, session
from flask_session import Session  # Importa Flask-Session
from flask_cors import CORS
import os
import random

# Configuración de Flask
app = Flask(__name__)
CORS(app, supports_credentials=True)

# Configuración de la sesión
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecretkey")
app.config["SESSION_TYPE"] = "filesystem"  # Usa el sistema de archivos para almacenar sesiones
app.config["SESSION_PERMANENT"] = False    # Las sesiones no serán permanentes
app.config["SESSION_USE_SIGNER"] = True    # Firma las sesiones para mayor seguridad
Session(app)  # Inicializa Flask-Session

# Base de conocimiento (diccionario simple para el ejemplo)
base_de_conocimiento = {
    "ansioso": "cuadro de ansiedad",
    "nervioso": "nerviosismo",
    "cansado": "fatiga",
    "estresado": "estrés",
    "angustiado": "angustia"
}

# Función para manejar la conversación
def manejar_conversacion(mensaje_usuario):
    # Inicializar sesión si no existe
    if "sintomas_recibidos" not in session:
        session["sintomas_recibidos"] = []
    if "respuestas_previas" not in session:
        session["respuestas_previas"] = []

    # Recuperar listas de la sesión
    sintomas_recibidos = session["sintomas_recibidos"]
    respuestas_previas = session["respuestas_previas"]

    # Respuestas generales
    respuestas_generales = [
        "¿Podrías contarme si hay algún otro síntoma que te preocupe?",
        "¿Hay algo más que quieras mencionar sobre cómo te sentís?",
        "¿Aparte de eso, qué otro malestar sentís?",
        "Entendido. ¿Podés decirme si tenés algún otro síntoma?"
    ]

    # Saludo inicial si no hay síntomas registrados
    if len(sintomas_recibidos) == 0:
        saludo_inicial = "¡Hola! ¿En qué puedo ayudarte hoy?"
        respuestas_previas.append(saludo_inicial)
        session["respuestas_previas"] = respuestas_previas
        session.modified = True
        return saludo_inicial

    # Evitar repetir preguntas sobre síntomas ya registrados
    if mensaje_usuario in sintomas_recibidos:
        respuesta = "Ya mencionaste ese síntoma. ¿Podrías contarme si hay algún otro síntoma que te preocupe?"
        respuestas_previas.append(respuesta)
        session["respuestas_previas"] = respuestas_previas
        session.modified = True
        return respuesta

    # Registrar el nuevo síntoma
    sintomas_recibidos.append(mensaje_usuario)
    session["sintomas_recibidos"] = sintomas_recibidos
    session.modified = True

    # Diagnóstico si hay más de 3 síntomas
    if len(sintomas_recibidos) >= 3:
        diagnosticos = [
            base_de_conocimiento.get(sintoma, "desconocido")
            for sintoma in sintomas_recibidos
        ]
        diagnosticos = [diag for diag in diagnosticos if diag != "desconocido"]

        if diagnosticos:
            respuesta_final = (
                f"En base a los síntomas que mencionaste ({', '.join(sintomas_recibidos)}), "
                f"podrías estar atravesando un estado relacionado con {', '.join(set(diagnosticos))}. "
                "Si lo considerás necesario, contactá con un profesional de la salud."
            )
        else:
            respuesta_final = (
                "Gracias por compartir cómo te sentís. No se encontró un diagnóstico en la base de conocimiento."
            )

        respuestas_previas.append(respuesta_final)
        session["respuestas_previas"] = respuestas_previas
        session.modified = True
        return respuesta_final

    # Continuar la conversación con preguntas generales
    respuesta = random.choice(respuestas_generales)
    respuestas_previas.append(respuesta)
    session["respuestas_previas"] = respuestas_previas
    session.modified = True
    return respuesta

# Ruta principal para manejar la conversación
@app.route("/asistente", methods=["POST"])
def asistente():
    try:
        # Verificar que el contenido sea JSON
        if not request.content_type or "application/json" not in request.content_type:
            return jsonify({"respuesta": "El encabezado 'Content-Type' debe ser 'application/json'."}), 400

        # Leer el cuerpo de la solicitud
        data = request.get_json()
        if not data or "mensaje" not in data:
            return jsonify({"respuesta": "Por favor, proporcioná un mensaje válido."}), 400

        mensaje_usuario = data["mensaje"].strip().lower()
        if not mensaje_usuario:
            return jsonify({"respuesta": "Por favor, proporcioná un mensaje no vacío."}), 400

        # Manejar la conversación
        respuesta = manejar_conversacion(mensaje_usuario)

        return jsonify({
            "respuesta": respuesta,
            "sintomas": session.get("sintomas_recibidos", []),
            "respuestas_previas": session.get("respuestas_previas", [])
        })

    except Exception as e:
        print(f"Error procesando la solicitud: {e}")
        return jsonify({"respuesta": "Ocurrió un error interno en el servidor.", "error": str(e)}), 500

# Ruta para reiniciar la conversación
@app.route("/reset", methods=["POST"])
def reset_sesion():
    session.clear()
    return jsonify({"respuesta": "La conversación se ha reiniciado. ¡Hola! ¿En qué puedo ayudarte?"})

# Iniciar el servidor Flask
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
