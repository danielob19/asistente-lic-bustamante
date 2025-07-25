import openai
import numpy as np
from numpy.linalg import norm

# 🧠 Base de intenciones con múltiples formulaciones por intención
intenciones_faq = [
    {
        "intencion": "obras_sociales",
        "formulaciones": [
            "¿Trabaja con obras sociales?",
            "¿Acepta medicinas prepagas?",
            "¿Puedo atenderme con mi obra social?",
            "¿Está en mi cartilla?",
            "¿Atiende por OSDE?",
            "¿Cubre mi plan de salud?",
            "atiende por obra social"
            "¿La consulta entra por prepaga?",
        ],
        "respuesta": (
            "El Lic. Daniel O. Bustamante no trabaja con obras sociales ni prepagas. Atiende únicamente de manera particular.\n\n"
            "Si deseás iniciar un proceso terapéutico, podés escribirle directamente por WhatsApp al +54 911 3310-1186."
        )
    },
    {
        "intencion": "duracion_sesion",
        "formulaciones": [
            "¿Cuánto dura la sesión?",
            "¿De qué duración son las consultas?",
            "¿Las sesiones cuánto tiempo toman?",
            "¿Qué duración tienen las sesiones?",
            "¿Son sesiones largas o cortas?",
        ],
        "respuesta": (
            "Las sesiones con el Lic. Daniel O. Bustamante tienen una duración aproximada de 50 minutos y se realizan por videoconsulta.\n\n"
            "La frecuencia puede variar según cada caso, pero generalmente se recomienda un encuentro semanal para favorecer el proceso terapéutico.\n\n"
            "Podés contactarlo por WhatsApp al +54 911 3310-1186 si querés coordinar una sesión."
        )
    },
    {
        "intencion": "servicios_ofrecidos",
        "formulaciones": [
            "¿Qué servicios ofrece?",
            "¿En qué puede ayudarme?",
            "¿Qué trata el Licenciado?",
            "¿Qué tipo de terapia brinda?",
            "¿Con qué temas trabaja?",
        ],
        "respuesta": (
            "El Lic. Daniel O. Bustamante brinda atención psicológica exclusivamente online, a través de videoconsultas.\n\n"
            "Entre los principales motivos de consulta que aborda se encuentran:\n"
            "- Psicoterapia individual para adultos (modalidad online)\n"
            "- Tratamiento de crisis emocionales\n"
            "- Abordaje de ansiedad, estrés y ataques de pánico\n"
            "- Procesos de duelo y cambios vitales\n"
            "- Estados anímicos depresivos\n"
            "- Problemas de autoestima y motivación\n"
            "- Dificultades vinculares y emocionales\n"
            "- Terapia de pareja online\n\n"
            "En caso de que desees contactar al Lic. Daniel O. Bustamante, podés hacerlo escribiéndole al WhatsApp +54 911 3310-1186, que con gusto responderá a tus inquietudes."
        )
    }
]

def generar_embeddings_faq():
    for item in intenciones_faq:
        item["embeddings"] = []
        for frase in item["formulaciones"]:
            response = openai.Embedding.create(
                model="text-embedding-ada-002",
                input=frase
            )
            embedding = response["data"][0]["embedding"]
            item["embeddings"].append(np.array(embedding))

def buscar_respuesta_semantica(mensaje: str, umbral=0.88) -> str | None:
    try:
        emb_usuario = openai.Embedding.create(
            model="text-embedding-ada-002",
            input=mensaje
        )["data"][0]["embedding"]
        emb_usuario = np.array(emb_usuario)

        mejor_score = 0
        mejor_respuesta = None

        for item in intenciones_faq:
            for emb in item.get("embeddings", []):
                score = np.dot(emb_usuario, emb) / (norm(emb_usuario) * norm(emb))
                if score > mejor_score and score >= umbral:
                    mejor_score = score
                    mejor_respuesta = item["respuesta"]

        return mejor_respuesta
    except Exception as e:
        print(f"❌ Error en detección semántica: {e}")
        return None

def buscar_respuesta_semantica_con_score(mensaje: str, umbral=0.88):
    try:
        emb_usuario = openai.Embedding.create(
            model="text-embedding-ada-002",
            input=mensaje
        )["data"][0]["embedding"]
        emb_usuario = np.array(emb_usuario)

        mejor_score = 0
        mejor_formulacion = None
        mejor_respuesta = None

        for item in intenciones_faq:
            for i, emb in enumerate(item.get("embeddings", [])):
                score = np.dot(emb_usuario, emb) / (norm(emb_usuario) * norm(emb))
                if score > mejor_score:
                    mejor_score = score
                    mejor_formulacion = item["formulaciones"][i]
                    mejor_respuesta = item["respuesta"]

        if mejor_score >= umbral:
            return mejor_formulacion, mejor_respuesta, mejor_score
        return None
    except Exception as e:
        print(f"❌ Error en buscar_respuesta_semantica_con_score: {e}")
        return None
