# cerebro_simulado.py

def predecir_evento_futuro(mensajes):
    # Análisis simple de proyección futura basada en contenido
    for mensaje in mensajes[::-1]:  # analizamos desde el más reciente
        if "me va a pasar" in mensaje or "seguro que terminaré" in mensaje:
            return mensaje
    return "sin predicción identificable"

def inferir_patron_interactivo(mensajes):
    if len(mensajes) < 3:
        return "patrón indefinido"
    if all("yo" in m.lower() for m in mensajes[-3:]):
        return "foco en sí mismo"
    if all("vos" in m.lower() or "usted" in m.lower() for m in mensajes[-3:]):
        return "interpelación al otro"
    return "sin patrón definido"

def evaluar_coherencia_mensaje(mensaje):
    if len(mensaje.split()) < 3:
        return "mensaje muy breve"
    if any(palabra in mensaje.lower() for palabra in ["odio", "muerte", "desaparecer"]):
        return "mensaje de riesgo"
    return "mensaje coherente"

def clasificar_estado_mental(mensajes):
    texto = " ".join(mensajes).lower()
    if any(palabra in texto for palabra in ["no tiene sentido", "todo me cuesta", "nada me entusiasma", "ya no me importa"]):
        return "apatía o anhedonia"
    if any(palabra in texto for palabra in ["no puedo más", "me duele todo", "me supera", "quiero llorar"]):
        return "agotamiento emocional"
    if any(palabra in texto for palabra in ["me van a lastimar", "siento peligro", "nadie me entiende", "me odian"]):
        return "estado defensivo o paranoide"
    return "estado emocional no definido"

def inferir_intencion_usuario(mensajes):
    if not mensajes:
        return "intención no clara"

    ultimo = mensajes[-1].lower()

    if "quiero ayuda" in ultimo or "necesito hablar" in ultimo:
        return "búsqueda de asistencia"

    if "solo estoy probando" in ultimo:
        return "curiosidad o prueba"

    patrones_cierre = [
        "ya no sé si vale la pena", 
        "creo que no me sirve", 
        "hasta acá llegué",
        "no quiero seguir", 
        "no tiene sentido seguir",
        "no me está ayudando", 
        "gracias, pero ya está", 
        "prefiero dejarlo", 
        "no quiero continuar"
    ]

    if any(pat in ultimo for pat in patrones_cierre):
        return "intención de cierre"

    return "intención no determinada"
