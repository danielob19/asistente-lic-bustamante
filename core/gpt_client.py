import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

def generar_respuesta_gpt(mensajes):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=mensajes,
        temperature=0.7,
        max_tokens=300
    )
    return response.choices[0].message["content"]
