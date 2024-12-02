@app.post("/asistente")
async def asistente(input_data: UserInput):
    try:
        user_id = input_data.user_id
        mensaje_usuario = input_data.mensaje.strip()

        if not mensaje_usuario:
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

        # Si la sesión ya no existe, indica que la conversación ha terminado
        if user_id not in user_sessions:
            return {
                "respuesta": (
                    "La conversación ha terminado. Si necesitas más ayuda, por favor inicia una nueva conversación."
                )
            }

        # Inicializar o incrementar el contador de interacciones
        if user_id not in user_sessions:
            user_sessions[user_id] = {"contador_interacciones": 0}

        user_sessions[user_id]["contador_interacciones"] += 1
        interacciones = user_sessions[user_id]["contador_interacciones"]

        # Si es la tercera interacción, sugerir contacto y reiniciar conversación
        if interacciones >= 3:
            user_sessions.pop(user_id, None)  # Eliminar sesión del usuario
            return {
                "respuesta": (
                    "Gracias por compartir cómo te sentís. Si lo considerás necesario, "
                    "contactá al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 "
                    "para una evaluación más profunda. La conversación ha terminado."
                )
            }

        # Generar respuesta usando OpenAI
        respuesta = await interactuar_con_openai(mensaje_usuario)
        return {"respuesta": respuesta}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
