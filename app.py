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

# Importar la base de conocimiento
from base_conocimiento import base_de_conocimiento

# Archivo para almacenar síntomas pendientes
archivo_sintomas_pendientes = "sintomas_pendientes.json"

# Crear el archivo si no existe
if not os.path.exists(archivo_sintomas_pendientes):
    with open(archivo_sintomas_pendientes, "w") as f:
        json.dump([], f)

# Frases iniciales y de continuación
frases_iniciales = [
    "¿Hola, en qué te puedo ayudar hoy?",
    "¿Qué malestar estás experimentando hoy?",
    "¿Cómo te sentís en este momento?"
]

frases_continuar = [
    "¿Aparte de eso, qué otro malestar sentís?",
    "¿Podrías contarme si hay algún otro síntoma que te preocupe?",
    "¿Hay algo más que quieras mencionar sobre cómo te sentís?"
]

frases_cierre = [
    "Gracias por compartir. ¿Hay algo más que quieras agregar?",
    "Entendido. ¿Sentís algún otro síntoma que deba saber?",
    "¿Te gustaría mencionar algo más sobre tu estado anímico?"
]

# Guardar síntoma no reconocido
def guardar_sintoma_pendiente(sintoma):
    """Guarda un síntoma no reconocido en el archivo JSON."""
    try:
        with open(archivo_sintomas_pendientes, "r") as f:
            sintomas_pendientes = json.load(f)

        if sintoma not in sintomas_pendientes:
            sintomas_pendientes.append(sintoma)

        with open(archivo_sintomas_pendientes, "w") as f:
            json.dump(sintomas_pendientes, f, indent=4)

    except Exception as e:
        print(f"Error guardando síntoma pendiente: {e}")

# Cotejar síntomas en la base de conocimiento
def cotejar_sintomas(sintomas):
    """Busca coincidencias en la base de conocimiento."""
    diagnosticos = {}
    for sintoma in sintomas:
        if sintoma in base_de_conocimiento:
            diagnostico = base_de_conocimiento[sintoma]
            diagnosticos[diagnostico] = diagnosticos.get(diagnostico, 0) + 1
    return diagnosticos

# Interpretar síntomas usando OpenAI
def interpretar_sintomas(mensaje_usuario):
    """Utiliza OpenAI para interpretar y normalizar los síntomas del usuario."""
    prompt = (
        f"El usuario menciona los siguientes síntomas: '{mensaje_usuario}'. "
        "Convierte estos síntomas al formato estándar utilizado en una base de conocimiento médica o psicológica."
    )
    try:
        respuesta_openai = openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            max_tokens=50,
            temperature=0.7
        )
        return respuesta_openai.choices[0].text.strip().split(",")
    except Exception as e:
        print(f"Error interpretando síntomas: {e}")
        return mensaje_usuario.split(",")

# Generar respuesta profesional
def generar_respuesta_general(sintomas, diagnostico=None):
    """Genera una respuesta profesional usando OpenAI."""
    if diagnostico:
        prompt = (
            f"Usuario menciona los síntomas: {', '.join(sintomas)}. "
            f"El diagnóstico presuntivo es: {diagnostico}. "
            "Genera una respuesta profesional estilo argentino que mencione los síntomas, el diagnóstico presuntivo y sugiera solicitar un turno diplomáticamente con el Lic. Daniel O. Bustamante."
        )
    else:
        prompt = (
            f"Usuario menciona los síntomas: {', '.join(sintomas)}. "
            "No se encontró un diagnóstico exacto en la base de conocimiento. Genera una respuesta profesional estilo argentino que mencione los síntomas y sugiera diplomáticamente solicitar un turno con el Lic. Daniel O. Bustamante."
        )
    try:
        respuesta_openai = openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            max_tokens=70,
            temperature=0.7
        )
        return respuesta_openai.choices[0].text.strip()
    except Exception as e:
        print(f"Error al conectar con OpenAI: {e}")
        return (
            f"En base a los síntomas que mencionaste ({', '.join(sintomas)}), "
            "te sugiero contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 para una evaluación más profunda."
        )

# Ruta del Asistente
@app.route("/asistente", methods=["POST"])
def asistente():
    try:
        data = request.get_json()
        mensaje_usuario = data.get("mensaje", "").strip().lower()

        if not mensaje_usuario:
            return jsonify({"respuesta": random.choice(frases_iniciales)})

        # Interpretar y normalizar los síntomas del usuario
        sintomas = interpretar_sintomas(mensaje_usuario)

        # Cotejar los síntomas
        diagnosticos = cotejar_sintomas(sintomas)
        diagnostico_presuntivo = max(diagnosticos, key=diagnosticos.get, default=None)

        if diagnostico_presuntivo and diagnosticos[diagnostico_presuntivo] >= 2:
            respuesta = generar_respuesta_general(sintomas, diagnostico_presuntivo)
            return jsonify({"respuesta": respuesta})

        # Registrar síntomas no reconocidos
        for sintoma in sintomas:
            if sintoma not in base_de_conocimiento:
                guardar_sintoma_pendiente(sintoma)

        # Preguntar por más información
        respuesta = random.choice(frases_continuar)
        return jsonify({"respuesta": respuesta})

    except Exception as e:
        print(f"Error procesando la solicitud: {e}")
        return jsonify({"respuesta": "Lo siento, ocurrió un error procesando tu solicitud."})

# Iniciar la aplicación
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
