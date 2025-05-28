import openai

def detectar_intencion_bifurcada(mensaje_usuario: str) -> dict:
    mensaje_usuario = mensaje_usuario.strip().lower()

    try:
        # Prompt para detectar intención general + posibles síntomas clínicos
        prompt = (
            f"Analizá el siguiente mensaje del usuario y clasificá su intención general como una de las siguientes opciones:\n"
            "- CLINICA: si expresa malestar vivido o pide ayuda emocional.\n"
            "- ADMINISTRATIVA: si consulta por servicios, precios, disponibilidad, etc.\n"
            "- MIXTA: si menciona un tema clínico pero de forma informativa.\n"
            "- INDEFINIDA: si no puede determinarse con claridad.\n\n"
            "Además, si detectás temas clínicos mencionados (como ansiedad, insomnio, tristeza, etc.), listalos.\n\n"
            "Mensaje: '''" + mensaje_usuario + "'''\n\n"
            "Respondé en formato JSON con estas claves:\n"
            "{\n"
            "  \"intencion_general\": \"CLINICA\" | \"ADMINISTRATIVA\" | \"MIXTA\" | \"INDEFINIDA\",\n"
            "  \"temas_administrativos\": [lista de términos clínicos detectados o vacío],\n"
            "  \"emociones_detectadas\": [opcional, si se detecta CLINICA o MIXTA con carga emocional]\n"
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
