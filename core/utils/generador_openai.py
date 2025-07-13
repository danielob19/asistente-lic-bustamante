# core/utils/generador_openai.py

import openai
import os

# ✅ Configurar la API key aquí, donde se usa
openai.api_key = os.getenv("OPENAI_API_KEY")

def generar_respuesta_con_openai(
    prompt: str,
    contador: int = None,
    user_id: str = None,
    mensaje_usuario: str = None,
    mensaje_original: str = None
) -> str:
    try:
        respuesta = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
            n=1
        )
        contenido = respuesta.choices[0].message.content.strip()

        # 🧾 Opcional: Log local (puede comentarse si no querés verborragia)
        print(f"🧠 OpenAI respondió ({contador=}) → {contenido}")

        return contenido
    except Exception as e:
        error_msg = f"[ERROR OPENAI] {str(e)}"
        print(error_msg)
        return error_msg
