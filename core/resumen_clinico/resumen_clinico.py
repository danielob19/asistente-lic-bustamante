from collections import Counter
import re
import psycopg2

from core.db.sintomas import obtener_coincidencias_sintomas_y_registrar
from core.db.registro import registrar_respuesta_openai, registrar_emocion, registrar_inferencia
from core.constantes import DATABASE_URL
from cerebro_simulado import predecir_evento_futuro, clasificar_estado_mental
from core.analisis_emocional import detectar_emociones_negativas, inferir_emocion_no_dicha


def generar_resumen_clinico_y_estado(session: dict, contador: int) -> str:
    mensajes = session.get("mensajes", [])
    emociones_acumuladas = session.get("emociones_detectadas", [])

    emociones_detectadas = detectar_emociones_negativas(" - ".join(mensajes)) or []
    emociones_unificadas = list(set(emociones_acumuladas + emociones_detectadas))
    session["emociones_detectadas"] = emociones_unificadas

    if not emociones_unificadas:
        print(f"⚠️ No se detectaron emociones al llegar a la interacción {contador}")
        return (
            "No se identificaron emociones predominantes en este momento. "
            "Te sugiero contactar al Lic. Bustamante al WhatsApp +54 911 3310-1186 para una evaluación más precisa."
        )

    coincidencias_sintomas = obtener_coincidencias_sintomas_y_registrar(emociones_unificadas)
    cuadro_predominante = (
        Counter(coincidencias_sintomas).most_common(1)[0][0]
        if len(coincidencias_sintomas) >= 2
        else "No se pudo establecer con certeza un estado emocional predominante."
    )

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
    return respuesta


def generar_resumen_interaccion_5(session, user_id, interaccion_id, contador):
    print("🧩 Generando resumen clínico en interacción 5")
    emociones_previas = session.get("emociones_detectadas", [])
    mensajes_previos = session["mensajes"]
    nuevas_emociones = []

    for mensaje in mensajes_previos:
        nuevas = detectar_emociones_negativas(mensaje) or []
        for emocion in nuevas:
            emocion = re.sub(r'[^\w\sáéíóúüñ]+$', '', emocion.lower().strip())
            if emocion not in emociones_previas:
                nuevas_emociones.append(emocion)

    if nuevas_emociones:
        session["emociones_detectadas"].extend(nuevas_emociones)
        for emocion in nuevas_emociones:
            registrar_emocion(emocion, f"interacción {contador}", user_id)

    estado_global = clasificar_estado_mental(mensajes_previos)
    if estado_global != "estado emocional no definido":
        print(f"📊 Estado global sintetizado: {estado_global}")
        registrar_inferencia(user_id, contador, "estado_mental", estado_global)

    try:
        conn = psycopg2.connect(DATABASE_URL)
        emocion_inferida = inferir_emocion_no_dicha(session["emociones_detectadas"], conn)
        conn.close()
    except Exception as e:
        print(f"⚠️ Error al conectar a la base para inferencia en interacción 5: {e}")
        emocion_inferida = None

    if emocion_inferida and emocion_inferida not in session["emociones_detectadas"]:
        session["emocion_inferida_5"] = emocion_inferida

    if session["emociones_detectadas"]:
        emociones_literal = ", ".join(session["emociones_detectadas"])
        resumen = (
            f"Por lo que mencionaste hasta ahora, se identifican las siguientes emociones: {emociones_literal}. "
            f"Impresiona ser un estado emocional predominantemente {estado_global}. "
        )
    else:
        resumen = (
            f"Por lo que mencionaste hasta ahora, se observa un malestar anímico que daría la impresión de corresponder "
            f"a un estado emocional predominantemente {estado_global}. "
        )

    if emocion_inferida:
        resumen += (
            f"Además, ¿dirías que también podrías estar atravesando cierta {emocion_inferida}? "
            f"Lo pregunto porque suele aparecer en casos similares."
        )
    else:
        resumen += "¿Te interesaría consultarlo con el Lic. Daniel O. Bustamante?"

    session["resumen_generado"] = True
    registrar_respuesta_openai(interaccion_id, resumen)
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

    try:
        conn = psycopg2.connect(DATABASE_URL)
        emocion_inferida = inferir_emocion_no_dicha(session["emociones_detectadas"], conn)
        conn.close()
    except Exception as e:
        print(f"⚠️ Error en inferencia conexión BD: {e}")
        emocion_inferida = None

    if emocion_inferida and emocion_inferida not in session["emociones_detectadas"]:
        session["emociones_detectadas"].append(emocion_inferida)
        registrar_emocion(emocion_inferida, f"confirmación de inferencia (interacción {contador})", user_id)
        session["emocion_inferida_9"] = emocion_inferida

    emociones_literal = ", ".join(session["emociones_detectadas"])
    respuesta = (
        f"Por lo que comentás, pues al malestar anímico que describiste anteriormente, "
        f"advierto que se suman {emociones_literal}, por lo que daría la impresión de que se trata "
        f"de un estado emocional predominantemente {estado_global}. "
    )

    if emocion_inferida:
        respuesta += (
            f"Además, ¿dirías que también podrías estar atravesando cierta {emocion_inferida}? "
            f"Lo pregunto porque suele aparecer en casos similares. "
        )

    respuesta += (
        "No obstante, para estar seguros se requiere de una evaluación psicológica profesional. "
        "Te sugiero que te contactes con el Lic. Bustamante. "
        "Lamentablemente, no puedo continuar con la conversación más allá de este punto."
    )

    session["resumen_generado"] = True
    registrar_respuesta_openai(interaccion_id, respuesta)
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
    return respuesta
