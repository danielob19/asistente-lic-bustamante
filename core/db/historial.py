from core.db.utilidades import ejecutar_consulta


def registrar_historial_clinico(
    user_id,
    emociones,
    sintomas,
    tema,
    respuesta_openai,
    sugerencia,
    fase_evaluacion,
    interaccion_id,
    fecha,
    fuente,
    eliminado
):
    query = """
    INSERT INTO historial_clinico_usuario (
        user_id,
        emociones,
        sintomas,
        tema,
        respuesta_openai,
        sugerencia,
        fase_evaluacion,
        interaccion_id,
        fecha,
        fuente,
        eliminado
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    valores = (
        user_id,
        emociones,
        sintomas,
        tema,
        respuesta_openai,
        sugerencia,
        fase_evaluacion,
        str(interaccion_id) if interaccion_id else None,
        fecha,
        fuente,
        eliminado
    )
    try:
        ejecutar_consulta(query, valores, commit=True)
    except Exception as e:
        print(f"🔴 Error al registrar historial clínico: {e}")

