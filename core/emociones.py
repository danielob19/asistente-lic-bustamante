from core.gpt_client import generar_respuesta_gpt

def detectar_emocion_gpt(mensaje_usuario):
    prompt = [
        {"role": "system", "content": "Detectá la emoción principal en este texto. Respondé solo con: tristeza, ansiedad, miedo, enojo, angustia o ninguna."},
        {"role": "user", "content": mensaje_usuario}
    ]
    emocion = generar_respuesta_gpt(prompt).strip().lower()
    return emocion if emocion in {"tristeza", "ansiedad", "miedo", "enojo", "angustia"} else None
