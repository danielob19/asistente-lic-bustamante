import re
import openai
import numpy as np
from numpy.linalg import norm

faq_respuestas = [
    {
        "pregunta": "¿Qué servicios ofrece?",
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
    },
    {
        "pregunta": "¿Cuánto dura la sesión?",
        "respuesta": (
            "Las sesiones con el Lic. Daniel O. Bustamante tienen una duración aproximada de 50 minutos y se realizan por videoconsulta.\n\n"
            "La frecuencia puede variar según cada caso, pero generalmente se recomienda un encuentro semanal para favorecer el proceso terapéutico.\n\n"
            "Podés contactarlo por WhatsApp al +54 911 3310-1186 si querés coordinar una sesión."
        )
    },
]

def generar_embeddings_faq():
    preguntas = [item["pregunta"] for item in faq_respuestas]
    response = openai.Embedding.create(
        model="text-embedding-ada-002",
        input=preguntas
    )
    for i, embedding in enumerate(response["data"]):
        faq_respuestas[i]["embedding"] = np.array(embedding["embedding"])

def es_sobre_obra_social(mensaje: str) -> bool:
    mensaje = mensaje.lower().strip()
    patrones = [
        r'\bobra[s]?\s*social(es)?\b',
        r'\bpre[p]?agas?\b',
        r'\bioma\b', r'\bosde\b', r'\bgaleno\b',
        r'\bswiss\s*medical\b', r'\bluis\s*pasteur\b',
        r'\bomint\b', r'\bmedicus\b', r'\baca\b',
        r'\bsancor\b', r'\bprevención\b',
        r'\bplan\s*(de)?\s*salud\b', r'\bplan\b.*\bsalud\b',
        r'\bcobertura\s*(m[eé]dica)?\b'
    ]
    return any(re.search(p, mensaje) for p in patrones)


def buscar_respuesta_semantica(mensaje: str, umbral=0.88) -> str | None:
    try:
        # Intercepción directa basada en intención
        if es_sobre_obra_social(mensaje):
            return (
                "El Lic. Daniel O. Bustamante no trabaja con obras sociales ni prepagas. "
                "Atiende únicamente de manera particular. "
                "Si deseás iniciar un proceso terapéutico, podés escribirle directamente por WhatsApp al +54 911 3310-1186."
            )

        # Resto del análisis por embeddings
        embedding_usuario = openai.Embedding.create(
            model="text-embedding-ada-002",
            input=mensaje
        )["data"][0]["embedding"]
        embedding_usuario = np.array(embedding_usuario)

        mejor_score = 0
        mejor_respuesta = None
        for item in faq_respuestas:
            emb_faq = item.get("embedding")
            if emb_faq is not None:
                similitud = np.dot(embedding_usuario, emb_faq) / (norm(embedding_usuario) * norm(emb_faq))
                if similitud > mejor_score and similitud >= umbral:
                    mejor_score = similitud
                    mejor_respuesta = item["respuesta"]

        return mejor_respuesta
    except Exception as e:
        print(f"❌ Error en detección semántica: {e}")
        return None


def buscar_respuesta_semantica_con_score(mensaje: str, umbral=0.88):
    try:
        embedding_usuario = openai.Embedding.create(
            model="text-embedding-ada-002",
            input=mensaje
        )["data"][0]["embedding"]
        embedding_usuario = np.array(embedding_usuario)

        mejor_score = 0
        mejor_pregunta = None
        mejor_respuesta = None

        for item in faq_respuestas:
            emb_faq = item.get("embedding")
            if emb_faq is not None:
                similitud = np.dot(embedding_usuario, emb_faq) / (norm(embedding_usuario) * norm(emb_faq))
                if similitud > mejor_score:
                    mejor_score = similitud
                    mejor_pregunta = item["pregunta"]
                    mejor_respuesta = item["respuesta"]

        if mejor_score >= umbral:
            return mejor_pregunta, mejor_respuesta, mejor_score
        return None
    except Exception as e:
        print(f"❌ Error en buscar_respuesta_semantica_con_score: {e}")
        return None
