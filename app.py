# Endpoint principal para interacción con el asistente
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
                "mensajes": [],
                "ultimo_mensaje": None,
            }
        else:
            user_sessions[user_id]["ultima_interaccion"] = time.time()

        # Incrementar contador de interacciones
        user_sessions[user_id]["contador_interacciones"] += 1
        interacciones = user_sessions[user_id]["contador_interacciones"]

        # Almacenar mensaje del usuario
        user_sessions[user_id]["mensajes"].append(mensaje_usuario)

        # Registro para depuración
        print(f"Usuario: {user_id}, Interacciones: {interacciones}, Mensajes: {user_sessions[user_id]['mensajes']}")

        # Bloquear cualquier interacción después de la quinta
        if interacciones > 5:
            user_sessions.pop(user_id, None)  # Asegurar que la sesión se elimina
            return {
                "respuesta": "La conversación ha finalizado. Si querés reiniciar, escribí **reiniciar**."
            }

        # Reinicio de conversación
        if mensaje_usuario == "reiniciar":
            user_sessions.pop(user_id, None)
            return {"respuesta": "La conversación ha sido reiniciada. Empezá de nuevo cuando quieras escribiendo **reiniciar**."}

        # Manejo de "sí"
        if mensaje_usuario in ["si", "sí", "si claro", "sí claro"]:
            if user_sessions[user_id]["ultimo_mensaje"] in ["si", "sí", "si claro", "sí claro"]:
                return {"respuesta": "Ya confirmaste eso. ¿Hay algo más en lo que pueda ayudarte?"}
            user_sessions[user_id]["ultimo_mensaje"] = mensaje_usuario
            return {"respuesta": "Entendido. ¿Podrías contarme más sobre lo que estás sintiendo?"}

        # Manejo de "no"
        if mensaje_usuario in ["no", "no sé", "tal vez"]:
            return {"respuesta": "Está bien, toma tu tiempo. Estoy aquí para escucharte."}

        # Respuesta durante las primeras interacciones (1 a 4)
        if interacciones < 5:
            respuesta_ai = await interactuar_con_openai(mensaje_usuario)
            return {"respuesta": respuesta_ai}

        # Quinta interacción: análisis completo
        if interacciones == 5:
            try:
                # Obtener todos los mensajes acumulados
                sintomas_usuario = " ".join(user_sessions[user_id]["mensajes"])
                print(f"Análisis de síntomas: {sintomas_usuario}")  # Registro de depuración

                # Analizar el mensaje para palabras clave y categorías
                resultado_analisis = analizar_mensaje_usuario(sintomas_usuario)
                print(f"Resultado del análisis: {resultado_analisis}")  # Registro de depuración

                # Generar respuesta final con OpenAI
                prompt = (
                    f"El usuario compartió los siguientes síntomas: \"{sintomas_usuario}\".\n\n"
                    f"Resultado del análisis: {resultado_analisis}\n\n"
                    "Redacta una respuesta profesional y empática que mencione los síntomas, posibles cuadros o estados, "
                    "y sugiera al usuario contactar al Lic. Daniel O. Bustamante para una evaluación más profunda."
                )

                respuesta_final = await interactuar_con_openai(prompt)
                print(f"Respuesta final generada: {respuesta_final}")  # Registro de depuración

                # Limpiar sesión después de responder
                user_sessions.pop(user_id, None)

                return {"respuesta": respuesta_final}
            except Exception as e:
                print(f"Error en el análisis o generación de respuesta final: {e}")
                raise HTTPException(status_code=500, detail="Lo siento, no pude procesar tu solicitud.")

    except Exception as e:
        print(f"Error interno: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
