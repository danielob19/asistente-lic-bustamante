import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import openai

# Configuración de Flask
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://licbustamante.com.ar"}})

# Configuración de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Importar la base de conocimiento
from base_conocimiento import base_de_conocimiento

# Archivo para almacenar los síntomas no reconocidos
archivo_sintomas_pendientes = "sintomas_pendientes.json"

# Cargar síntomas pendientes existentes
if not os.path.exists(archivo_sintomas_pendientes):
    with open(archivo_sintomas_pendientes, "w") as f:
        json.dump([], f)  # Crear archivo vacío

def guardar_sintoma_pendiente(sintoma):
    """Guarda un síntoma no reconocido en el archivo JSON."""
    try:
        with open(archivo_sintomas_pendientes, "r") as f:
            sintomas_pendientes = json.load(f)
        
        if sintoma not in sintomas_pendientes:
            sintomas_pendientes.append(sintoma)

        with open(archivo_sintomas_pendientes, "w") as f:
            json.dump(sintomas_pendientes, f, indent=4)
        
        print(f"Sintoma pendiente guardado: {sintoma}")
    except Exception as e:
        print(f"Error guardando síntoma pendiente: {e}")

# Ruta principal del asistente
@app.route("/asistente", methods=["POST"])
def asistente():
    try:
        data = request.get_json()
        mensaje_usuario = data.get("mensaje", "").strip().lower()

        if not mensaje_usuario:
            return jsonify({"respuesta": "Por favor, proporciona un mensaje válido."})

        # Buscar en la base de conocimiento local
        if mensaje_usuario in base_de_conocimiento:
            diagnostico = base_de_conocimiento[mensaje_usuario]
            return jsonify({
                "respuesta": f"Según los síntomas mencionados: '{mensaje_usuario}', podría tratarse de un {diagnostico}. "
                            "Te sugiero contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 para una evaluación más detallada."
            })

        # Si no se encuentra, guardar el síntoma como pendiente
        guardar_sintoma_pendiente(mensaje_usuario)

        # Usar OpenAI para generar una respuesta tentativa
        respuesta_openai = openai.Completion.create(
            engine="text-davinci-003",
            prompt=f"¿Qué puede significar el síntoma: {mensaje_usuario}?",
            max_tokens=100
        )
        return jsonify({
            "respuesta": respuesta_openai['choices'][0]['text'].strip(),
            "nota": "Este síntoma no está en la base de conocimiento y ha sido registrado para clasificarlo posteriormente."
        })

    except Exception as e:
        print(f"Error procesando la solicitud: {e}")
        return jsonify({"respuesta": "Lo siento, ocurrió un error procesando tu solicitud."})

# Ruta para obtener los síntomas pendientes
@app.route("/sintomas_pendientes", methods=["GET"])
def obtener_sintomas_pendientes():
    try:
        with open(archivo_sintomas_pendientes, "r") as f:
            sintomas_pendientes = json.load(f)
        return jsonify({"sintomas_pendientes": sintomas_pendientes})
    except Exception as e:
        print(f"Error obteniendo síntomas pendientes: {e}")
        return jsonify({"respuesta": "Error al obtener los síntomas pendientes."})

# Iniciar la aplicación
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
