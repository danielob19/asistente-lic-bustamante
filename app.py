# Nueva función para analizar síntomas y categorías por interacción final
def analizar_sintomas_categoria_final(sintomas_usuario):
    try:
        conexion = sqlite3.connect(DB_PATH)
        cursor = conexion.cursor()
        categorias = {}

        for sintoma in sintomas_usuario:
            cursor.execute("SELECT categoria FROM palabras_clave WHERE palabra LIKE ?", (f"%{sintoma}%",))
            resultados = cursor.fetchall()
            for categoria, in resultados:
                if categoria in categorias:
                    categorias[categoria].append(sintoma)
                else:
                    categorias[categoria] = [sintoma]

        conexion.close()
        return categorias
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al analizar síntomas: {str(e)}")

@app.post("/asistente")
async def asistente(input_data: UserInput):
    try:
        user_id = input_data.user_id
        mensaje_usuario = input_data.mensaje.strip().lower()

        if not mensaje_usuario:
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

        # Inicializar sesión si no existe
        if user_id not in user_sessions:
            user_sessions[user_id] = {
                "contador_interacciones": 0,
                "ultima_interaccion": time.time(),
                "ultimo_mensaje": None,
                "sintomas": []
            }
        else:
            user_sessions[user_id]["ultima_interaccion"] = time.time()

        user_sessions[user_id]["contador_interacciones"] += 1
        interacciones = user_sessions[user_id]["contador_interacciones"]

        # Reinicio de conversación
        if mensaje_usuario == "reiniciar":
            if user_id in user_sessions:
                user_sessions.pop(user_id)
                return {"respuesta": "La conversación ha sido reiniciada. Empezá de nuevo cuando quieras."}
            else:
                return {"respuesta": "No se encontró una sesión activa. Empezá una nueva conversación cuando quieras."}

        # Manejo de "sí"
        if mensaje_usuario in ["si", "sí", "si claro", "sí claro"]:
            if user_sessions[user_id]["ultimo_mensaje"] in ["si", "sí", "si claro", "sí claro"]:
                return {"respuesta": "Ya confirmaste eso. ¿Hay algo más en lo que pueda ayudarte?"}
            user_sessions[user_id]["ultimo_mensaje"] = mensaje_usuario
            return {"respuesta": "Entendido. ¿Qué más puedo hacer por vos?"}

        # Detectar y registrar nuevas palabras clave
        palabras_existentes = obtener_palabras_clave()
        nuevas_palabras = [
            palabra for palabra in mensaje_usuario.split() if palabra not in palabras_existentes
        ]
        for palabra in nuevas_palabras:
            registrar_palabra_clave(palabra, "categoría pendiente")

        # Agregar palabras del mensaje como posibles síntomas
        user_sessions[user_id]["sintomas"].extend(mensaje_usuario.split())

        # Mensaje de finalización de conversación con análisis de síntomas
        if interacciones >= 6:
            sintomas_usuario = user_sessions[user_id]["sintomas"]
            categorias = analizar_sintomas_categoria_final(sintomas_usuario)
            categorias_str = ". ".join(
                f"Categoría: {categoria}. Síntomas: {', '.join(sintomas)}" for categoria, sintomas in categorias.items()
            )

            return {
                "respuesta": (
                    "Si bien tengo que dar por terminada esta conversación, no obstante si lo considerás necesario, "
                    "te sugiero contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 "
                    "para una evaluación más profunda de tu condición emocional. "
                    f"Aquí tienes un resumen de los síntomas detectados y sus categorías: {categorias_str}. "
                    "Si querés reiniciar un nuevo chat escribí: reiniciar."
                )
            }

        if interacciones == 5:
            sintomas_usuario = user_sessions[user_id]["sintomas"]
            categorias = analizar_sintomas_categoria_final(sintomas_usuario)
            categorias_str = ". ".join(
                f"Categoría: {categoria}. Síntomas: {', '.join(sintomas)}" for categoria, sintomas in categorias.items()
            )

            return {
                "respuesta": (
                    "Comprendo perfectamente. Si lo considerás necesario, "
                    "te sugiero contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 "
                    "quien podrá ayudarte a partir de una evaluación más profunda de tu situación personal. "
                    f"Aquí tienes un resumen de los síntomas detectados y sus categorías: {categorias_str}."
                )
            }

        # Interacción con OpenAI
        respuesta = await interactuar_con_openai(mensaje_usuario)
        return {"respuesta": respuesta}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
