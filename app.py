from flask import Flask, request, jsonify, session
from flask_cors import CORS
import os
import random
from base_de_conocimiento import base_de_conocimiento  # Importación unificada

# Configuración de Flask
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://licbustamante.com.ar"}})
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecretkey")  # Necesario para sesiones


def manejar_conversacion(mensaje_usuario):
    # Recuperar o inicializar los síntomas y respuestas desde la sesión
    sintomas_recibidos = session.get("sintomas_recibidos", [])
    respuestas_previas = session.get("respuestas_previas", [])

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
        session["sintomas_recibidos"] = []  # Asegurarse de inicializar correctamente
        return saludo_inicial

    # Evitar repetir preguntas o síntomas ya registrados
    if mensaje_usuario in sintomas_recibidos:
        respuesta = "Ya mencionaste ese síntoma. ¿Podrías contarme si hay algún otro síntoma que te preocupe?"
        respuestas_previas.append(respuesta)
        session["respuestas_previas"] = respuestas_previas
        return respuesta

    # Agregar el nuevo síntoma
    sintomas_recibidos.append(mensaje_usuario)
    session["sintomas_recibidos"] = sintomas_recibidos  # Actualizar síntomas en la sesión

    # Finalizar automáticamente si hay más de 3 síntomas
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
                "Si lo considerás necesario, contactá al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 "
                "para una evaluación más profunda. Gracias por compartir cómo te sentís."
            )
        else:
            respuesta_final = (
                "Gracias por compartir cómo te sentís. Si considerás necesario, contactá al Lic. Daniel O. Bustamante "
                "al WhatsApp +54 911 3310-1186 para una consulta más detallada."
            )

        respuestas_previas.append(respuesta_final)
        session["respuestas_previas"] = respuestas_previas
        return respuesta_final

    # Continuar la conversación con preguntas variadas
    respuesta = random.choice(respuestas_generales)
    respuestas_previas.append(respuesta)
    session["respuestas_previas"] = respuestas_previas
    return respuesta


# Ruta para manejar la conversación
@app.route("/asistente", methods=["POST"])
def asistente():
    try:
        # Verificar encabezado Content-Type
        if not request.content_type or 'application/json' not in request.content_type:
            return jsonify({"respuesta": "El encabezado 'Content-Type' debe ser 'application/json'."}), 415

        # Leer el mensaje del usuario desde el cuerpo de la solicitud
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


# Ruta para reiniciar la sesión (opcional)
@app.route("/reset", methods=["POST"])
def reset_sesion():
    session.clear()
    return jsonify({"respuesta": "La conversación se ha reiniciado. ¡Hola! ¿En qué puedo ayudarte?"})


# Iniciar la aplicación
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
