from collections import Counter
from core.db.sintomas import obtener_sintomas_con_estado_emocional, registrar_sintoma
from core.db.registro import registrar_emocion
from core.utils.palabras_irrelevantes import palabras_irrelevantes
from core.utils_contacto import es_consulta_contacto
from core.funciones_asistente import detectar_emociones_negativas
from core.utils.generador_openai import generar_respuesta_con_openai
import re

# core/funciones_clinicas.py

def hay_contexto_clinico_anterior(user_id: str, contador: int, sesiones: dict) -> bool:
    """
    Evalúa si existe contexto clínico previo para un usuario determinado.
    Retorna True si el usuario ya tiene emociones registradas y el contador es mayor o igual a 6.
    """
    if user_id not in sesiones:
        return False
    if contador < 6:
        return False
    return bool(sesiones[user_id].get("emociones_detectadas"))


# Análisis de texto del usuario
def analizar_texto(mensajes_usuario):
    """
    Analiza los mensajes del usuario para detectar coincidencias con los síntomas almacenados
    y muestra un cuadro probable y emociones o patrones de conducta adicionales detectados.
    """
    sintomas_existentes = obtener_sintomas_con_estado_emocional()
    if not sintomas_existentes:
        return "No se encontraron síntomas en la base de datos para analizar."

    keyword_to_cuadro = {sintoma.lower(): cuadro for sintoma, cuadro in sintomas_existentes}
    sintomas_registrados = {sintoma.lower() for sintoma, _ in sintomas_existentes}

    coincidencias = []
    emociones_detectadas = []
    nuevos_sintomas = []

    for mensaje in mensajes_usuario:
        user_words = mensaje.lower().split()
        user_words = [
            palabra for palabra in user_words
            if palabra not in palabras_irrelevantes and len(palabra) > 2 and palabra.isalpha()
        ]

        for palabra in user_words:
            if palabra in keyword_to_cuadro:
                coincidencias.append(keyword_to_cuadro[palabra])
            elif palabra not in nuevos_sintomas:
                nuevos_sintomas.append(palabra)

    # Registrar síntomas nuevos sin cuadro clínico
    for sintoma in nuevos_sintomas:
        if sintoma not in sintomas_registrados:
            registrar_sintoma(sintoma, None)

    # Generar emociones detectadas si hay pocas coincidencias
    if len(coincidencias) < 2:
        texto_usuario = " ".join(mensajes_usuario)
        prompt = (
            f"Detectá emociones negativas o patrones emocionales con implicancia clínica en el siguiente texto del usuario:\n\n"
            f"{texto_usuario}\n\n"
            "Identificá únicamente términos emocionalmente relevantes (individuales o compuestos), separados por comas, sin explicaciones adicionales.\n\n"
            "Si el contenido no incluye ningún elemento clínico relevante, respondé únicamente con 'ninguna'."
        )

        try:
            emociones_detectadas = generar_respuesta_con_openai(prompt).split(",")
            emociones_detectadas = [
                emocion.strip().lower() for emocion in emociones_detectadas
                if emocion.strip().lower() not in palabras_irrelevantes
            ]

            for emocion in emociones_detectadas:
                registrar_sintoma(emocion, "patrón emocional detectado")

        except Exception as e:
            print(f"Error al usar OpenAI para detectar emociones: {e}")

    if not coincidencias and not emociones_detectadas:
        return "No se encontraron suficientes coincidencias para determinar un cuadro probable."

    respuesta = ""
    if coincidencias:
        category_counts = Counter(coincidencias)
        cuadro_probable, _ = category_counts.most_common(1)[0]
        respuesta = (
            f"Con base en los síntomas detectados ({', '.join(set(coincidencias))}), "
            f"el malestar emocional predominante es: {cuadro_probable}. "
        )

    if emociones_detectadas:
        respuesta += (
            f"Además, notamos emociones o patrones de conducta humanos como {', '.join(set(emociones_detectadas))}, "
            f"por lo que sugiero solicitar una consulta con el Lic. Daniel O. Bustamante escribiendo al WhatsApp "
            f"+54 911 3310-1186 para una evaluación más detallada."
        )

    return respuesta



# 🎯 Generar frase disparadora según emoción detectada
def generar_disparador_emocional(emocion):
    disparadores = {
        "tristeza": "La tristeza puede ser muy pesada. A veces aparece sin aviso y cuesta ponerla en palabras.",
        "ansiedad": "La ansiedad a veces no tiene una causa clara, pero se siente intensamente en el cuerpo y en los pensamientos.",
        "culpa": "La culpa suele cargar con cosas no dichas o no resueltas.",
        "enojo": "El enojo puede ser una forma de defensa frente a algo que dolió primero.",
        "miedo": "El miedo muchas veces se disfraza de prudencia o de silencio, pero su impacto se nota.",
        "confusión": "La confusión puede surgir cuando algo en nuestro mundo interno se mueve sin aviso.",
        "desgano": "A veces el desgano no es flojera, sino cansancio de sostener tanto por dentro.",
        "agotamiento": "El agotamiento emocional aparece cuando dimos mucho y recibimos poco o nada.",
        "soledad": "La soledad puede sentirse incluso rodeado de personas. A veces es una falta de resonancia más que de compañía."
    }
    return disparadores.get(emocion.lower())


# 🧾 Respuesta profesional para mensajes fuera de contexto clínico o emocional
def respuesta_default_fuera_de_contexto():
    return (
        "Este espacio está destinado exclusivamente a consultas vinculadas al bienestar emocional y psicológico. "
        "Si lo que querés compartir tiene relación con alguna inquietud personal, emocional o clínica, "
        "estoy disponible para acompañarte desde ese lugar."
    )


# 🧼 Estandarizar emoción detectada (p. ej. quitar puntuación final)
def estandarizar_emocion_detectada(emocion: str) -> str:
    emocion = emocion.strip().lower()
    emocion = re.sub(r"[.,;:!¡¿?]+$", "", emocion)
    return emocion

def _inferir_por_db_o_openai(user_id: str, texto: str, session: dict):
    conn = get_connection()
    try:
        sintomas = detectar_sintomas_db(conn, texto)
        rank = inferir_cuadros(conn, sintomas)
        tiene_evid, cuadro_top, aporta = decidir(rank, umbral_coincidencias=2)

        if tiene_evid:
            # voz clínica breve + pregunta de profundización
            msg = (
                f"Por lo que mencionás ({', '.join(aporta)}), "
                f"podría tratarse de {cuadro_top.lower()}. "
                "¿Notás también preocupaciones intensas, temores o evitación de ciertas situaciones?"
            )
            return {"fuente": "db", "cuadro_probable": cuadro_top, "mensaje": msg, "sintomas": [s['nombre'] for s in sintomas]}

        if sintomas:
            unico = sorted(set(s["nombre"] for s in sintomas))
            msg = (
                f"Mencionaste {', '.join(unico)}. "
                "Para ubicarlo mejor, contame otro síntoma frecuente (p. ej., mareos, sensación de irrealidad, sudoración, temblores)."
            )
            return {"fuente": "db_necesita_mas", "cuadro_probable": None, "mensaje": msg, "sintomas": unico}

        # fallback OpenAI si la DB no matchea nada
        prompt = (
            "Actuá como psicólogo humano y orientativo (no diagnóstico). "
            "Dado el mensaje del usuario, inferí un cuadro probable si hay base; si falta evidencia, pedí 1 síntoma adicional. "
            f"Usuario: {texto}"
        )
        ia = generar_respuesta_con_openai(prompt)
        return {"fuente": "openai", "cuadro_probable": None, "mensaje": ia, "sintomas": []}
    finally:
        try:
            conn.close()
        except:
            pass


