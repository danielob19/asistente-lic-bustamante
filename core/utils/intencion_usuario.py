import openai

def detectar_intencion_bifurcada(mensaje_usuario: str) -> dict:
    mensaje_usuario = mensaje_usuario.strip().lower()

    try:
        # Prompt para detectar intención general + posibles síntomas clínicos
        prompt = (
            f"Analizá el siguiente mensaje del usuario y clasificá su intención general como una de las siguientes opciones:\n"
            "- CLINICA: si expresa un malestar emocional personal vivido en carne propia (ej. 'me siento mal', 'estoy angustiado', 'no tengo ganas de nada').\n"
            "- ADMINISTRATIVA: si pregunta por servicios, si 'atienden ansiedad', si consulta por temas tratados, precios, agenda, etc.\n"
            "- MIXTA: si menciona un tema clínico pero de forma informativa, sin hablar de sí mismo.\n"
            "- INDEFINIDA: si no se puede determinar con claridad.\n\n"
            "⚠️ Instrucciones adicionales:\n"
            "- No clasifiques como CLINICA si el usuario solo pregunta por un síntoma sin describir cómo lo vive.\n"
            "- Si se detecta un síntoma (como ansiedad, insomnio, tristeza) pero no se menciona malestar personal, clasificá como MIXTA o ADMINISTRATIVA.\n"
            "- Solo si el mensaje transmite sufrimiento subjetivo o emocional vivido en primera persona, clasificá como CLINICA.\n\n"
            "Además, si detectás temas clínicos mencionados, listalos por separado.\n\n"
            f"Mensaje: '''{mensaje_usuario}'''\n\n"
            "Respondé en formato JSON con estas claves:\n"
            "{\n"
            "  \"intencion_general\": \"CLINICA\" | \"ADMINISTRATIVA\" | \"MIXTA\" | \"INDEFINIDA\",\n"
            "  \"temas_administrativos\": [lista de temas clínicos detectados o vacío],\n"
            "  \"emociones_detectadas\": [si se detecta CLINICA o MIXTA con emoción presente]\n"
            "}"
        )

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.0
        )

        import json
        raw = response.choices[0].message["content"]
        resultado = json.loads(raw)

        # Validación mínima
        if "intencion_general" not in resultado:
            resultado["intencion_general"] = "INDEFINIDA"

        if "temas_administrativos" not in resultado:
            resultado["temas_administrativos"] = []

        if "emociones_detectadas" not in resultado:
            resultado["emociones_detectadas"] = []

        return resultado

    except Exception as e:
        print(f"❌ Error en detectar_intencion_bifurcada: {e}")
        return {
            "intencion_general": "INDEFINIDA",
            "temas_administrativos": [],
            "emociones_detectadas": []
        }
