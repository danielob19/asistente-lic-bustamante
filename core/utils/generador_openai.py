import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

def generar_respuesta_con_openai(prompt: str) -> str:
    try:
        respuesta = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
            n=1
        )
        return respuesta.choices[0].message.content.strip()
    except Exception as e:
        return f"[ERROR OPENAI] {str(e)}"
