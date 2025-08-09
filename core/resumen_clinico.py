from collections import Counter
import re
import random
import openai  # ✅ Necesario para funciones que usan ChatCompletion

from core.db.registro import registrar_respuesta_openai, registrar_emocion, registrar_inferencia
from cerebro_simulado import predecir_evento_futuro, clasificar_estado_mental
from core.funciones_asistente import detectar_emociones_negativas
from core.utils.clinico_contexto import inferir_emocion_no_dicha


def generar_resumen_clinico_y_estado(session: dict, contador: int) -> str:
    mensajes = session.get("mensajes", [])
    emociones_acumuladas = session.get("emociones_detectadas", [])

    emociones_detectadas = detectar_emociones_negativas(" - ".join(mensajes)) or []
    emociones_unificadas = list(set(emociones_acumuladas + emociones_detectadas))
    session["emociones_detectadas"] = emociones_unificadas

    if not emociones_unificadas:
        print(f"⚠️ No se detectaron emociones al llegar a la interacción {contador}")
        respuesta = (
            "No se identificaron emociones predominantes en este momento. "
            "Te sugiero contactar al Lic. Bustamante al WhatsApp +54 911 3310-1186 para una evaluación más precisa."
        )
        session["ultimas_respuestas"].append(respuesta)
        user_sessions[session["user_id"]] = session
        return respuesta


    
    coincidencias_sintomas = []
    cuadro_predominante = None


    
    emociones_literal = " - ".join(emociones_unificadas[:3])

    respuesta = (
        f"Con base a lo que has descripto —{emociones_literal}—, "
        f"pareciera ser que el malestar emocional predominante es: {cuadro_predominante}."
    )

    if contador in [5, 9, 10]:
        respuesta += (
            " ¿Te interesaría consultarlo con el Lic. Daniel O. Bustamante? "
            "Podés escribirle al WhatsApp +54 911 3310-1186 para una evaluación más detallada."
        )

    print(f"📋 Resumen clínico generado correctamente en interacción {contador}")
    session["mensajes"].clear()
    session["ultimas_respuestas"].append(respuesta)
    user_sessions[session["user_id"]] = session
    return respuesta



def generar_resumen_interaccion_5(session, user_id, interaccion_id, contador, user_sessions):
    print("🧩 Generando resumen clínico en interacción 5")

    emociones_previas = session.get("emociones_detectadas", [])
    mensajes_previos = session.get("mensajes", [])
    nuevas_emociones = []

    # Detectar nuevas emociones en los mensajes previos
    nuevas = detectar_emociones_negativas(mensajes_previos) or []
    for emocion in nuevas:
        emocion = re.sub(r"[^\w\sáéíóúüñ]+$", "", emocion.lower().strip())
        if emocion not in emociones_previas:
            nuevas_emociones.append(emocion)

    if nuevas_emociones:
        session["emociones_detectadas"].extend(nuevas_emociones)
        for emocion in nuevas_emociones:
            registrar_emocion(emocion, f"interacción {contador}", user_id)

    estado_global = clasificar_estado_mental(session["emociones_detectadas"])
    if estado_global != "estado emocional no definido":
        print(f"📊 Estado global sintetizado: {estado_global}")
        registrar_inferencia(user_id, contador, "estado_mental", estado_global)

    resumen = ""
    if session["emociones_detectadas"]:
        emociones_literal = ", ".join(session["emociones_detectadas"])
        resumen = (
            f"En base a lo que mencionaste hasta ahora, se observan al menos las siguientes emociones: {emociones_literal}, "
            f"lo que podría indicar un estado emocional predominantemente {estado_global}."
        )
    else:
        resumen = (
            "Por lo que mencionaste hasta ahora, no se detectan emociones claras, aunque podría haber un estado emocional relevante."
        )

    # Guardar resumen en la sesión
    session["resumen_generado"] = True
    session.setdefault("ultimas_respuestas", []).append(resumen)
    registrar_respuesta_openai(interaccion_id, resumen)

    # ✅ Guardar cambios en la sesión global
    user_sessions[user_id] = session

    return resumen




def generar_resumen_interaccion_9(session, user_id, interaccion_id, contador):
    print("🧩 Generando resumen clínico en interacción 9")
    mensajes_6_a_9 = session["mensajes"][-4:]
    emociones_nuevas = []

    for mensaje in mensajes_6_a_9:
        nuevas = detectar_emociones_negativas(mensaje) or []
        for emocion in nuevas:
            emocion = re.sub(r'[^\w\sáéíóúüñ]+$', '', emocion.lower().strip())
            if emocion not in session["emociones_detectadas"]:
                emociones_nuevas.append(emocion)

    if emociones_nuevas:
        session["emociones_detectadas"].extend(emociones_nuevas)
        for emocion in emociones_nuevas:
            registrar_emocion(emocion, f"interacción {contador}", user_id)

    estado_global = clasificar_estado_mental(session["mensajes"])
    if estado_global != "estado emocional no definido":
        print(f"📊 Estado global sintetizado: {estado_global}")
        registrar_inferencia(user_id, contador, "estado_mental", estado_global)

    

    emocion_inferida = inferir_emocion_no_dicha(session["emociones_detectadas"])


    if emocion_inferida and emocion_inferida not in session["emociones_detectadas"]:
        session["emociones_detectadas"].append(emocion_inferida)
        registrar_emocion(emocion_inferida, f"confirmación de inferencia (interacción {contador})", user_id)
        session["emocion_inferida_9"] = emocion_inferida

    emociones_literal = ", ".join(session["emociones_detectadas"])
    frase_diagnostica = random.choice([
        "Se observa",
        "Impresiona ser",
        "Podría tratarse de",
        "Da la sensación de ser",
        "Normalmente se trata de un"
    ])

    respuesta = (
        f"Por lo que comentás, pues al malestar anímico que describiste anteriormente, "
        f"advierto que se suman {emociones_literal}, por lo que {frase_diagnostica.lower()} "
        f"un estado emocional predominantemente {estado_global}. "
    )

    if emocion_inferida:
        respuesta += (
            f"Además, se infiere también cierta {emocion_inferida}, ya que suele estar presente en combinaciones emocionales como las que expresaste."
        )

    session["resumen_generado"] = True
    registrar_respuesta_openai(interaccion_id, respuesta)
    session["ultimas_respuestas"].append(respuesta)
    user_sessions[user_id] = session
    return respuesta



def generar_resumen_interaccion_10(session, user_id, interaccion_id, contador):
    print("🔒 Cierre definitivo activado en la interacción 10")

    emocion_inferida = session.get("emocion_inferida_9")
    mensaje_usuario_actual = session["mensajes"][-1] if session["mensajes"] else ""

    if emocion_inferida and (
        emocion_inferida in mensaje_usuario_actual
        or "sí" in mensaje_usuario_actual
        or "me pasa" in mensaje_usuario_actual
    ):
        if emocion_inferida not in session["emociones_detectadas"]:
            session["emociones_detectadas"].append(emocion_inferida)
            registrar_emocion(emocion_inferida, "confirmación de inferencia (interacción 10)", user_id)

    resumen_total = generar_resumen_clinico_y_estado(session, contador)
    session["resumen_clinico_total"] = resumen_total

    respuesta = (
        "He encontrado interesante nuestra conversación, pero para profundizar más en el análisis de tu malestar, "
        "sería ideal que consultes con un profesional. Por ello, te sugiero que te contactes con el Lic. Bustamante. "
        "Lamentablemente, no puedo continuar con la conversación más allá de este punto."
    )

    prediccion = predecir_evento_futuro(session["mensajes"])
    if prediccion != "sin predicción identificada":
        print(f"🔮 Proyección detectada: {prediccion}")
        registrar_inferencia(user_id, contador, "prediccion", prediccion)
        respuesta += f" Por otra parte, se identificó que mencionaste una posible consecuencia o desenlace: {prediccion}."

    registrar_respuesta_openai(interaccion_id, respuesta)
    session["ultimas_respuestas"].append(respuesta)
    user_sessions[user_id] = session
    return respuesta
