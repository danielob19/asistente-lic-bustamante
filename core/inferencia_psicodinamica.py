import random

# ------------------------ Selección de estilo ------------------------

def seleccionar_estilo_redaccion() -> str:
    estilos = [
        "clasico",
        "inferencial",
        "estructural",
        "fenomenologico",
        "breve",
        "integrativo",
        "narrativo"  # ✅ Nuevo estilo agregado
    ]
    return random.choice(estilos)

# ------------------------ Reformulación narrativa ------------------------

def reformular_estilo_narrativo(mensaje_usuario: str) -> str:
    """
    Reformula el estilo narrativo post-cierre definitivo para evitar repeticiones
    y aportar matices clínicos distintos según el contenido expresado.
    """

    introducciones = [
        "Tu forma de expresarte permite entrever que existe algo que no ha sido completamente simbolizado.",
        "Lo que comentás sugiere un trasfondo emocional más profundo, aún no del todo procesado.",
        "Pareciera que hay un hilo subjetivo persistente que atraviesa lo que has expresado.",
        "Se vislumbra una tonalidad emocional que no ha podido ser integrada del todo.",
        "En tu modo de decir, se advierte una constancia afectiva no elaborada."
    ]

    clausuras = [
        "Como mencioné previamente, no puedo continuar la conversación desde aquí.",
        "Lamentablemente, no estoy habilitado para proseguir con esta interacción.",
        "Mi participación concluye en este punto por razones clínicas y éticas.",
        "Desde este espacio ya no puedo continuar la interacción de forma productiva.",
        "Es importante que, si deseás profundizar, lo hagas con un profesional."
    ]

    estilo = random.choice(introducciones) + " " + random.choice(clausuras)
    return estilo

# ------------------------ Reformulación según estilo ------------------------

def reformular_hipotesis(base: str, estilo: str) -> str:
    if estilo == "clasico":
        return base
    elif estilo == "inferencial":
        return base.replace("Podría estar operando", "Da la impresión de que se configura").replace("y el", "y un")
    elif estilo == "estructural":
        return "Se sugiere un conflicto estructural entre demandas internas y la vivencia de insuficiencia afectiva."
    elif estilo == "fenomenologico":
        return "La experiencia parece teñida por una oscilación entre búsqueda de aprobación y temor a no ser suficiente."
    elif estilo == "breve":
        return "Surge una tensión entre necesidad de validación y miedo al rechazo."
    elif estilo == "integrativo":
        return "Podría tratarse de un patrón donde el deseo de ser aceptado convive con el temor profundo a la desaprobación."
    elif estilo == "narrativo":
        return reformular_estilo_narrativo(base)
    else:
        return base  # fallback

# ------------------------ Hipótesis psicodinámica principal ------------------------

def generar_hipotesis_psicodinamica(emociones_detectadas: list, mensajes: list) -> str:
    """
    Genera una hipótesis psicodinámica tentativa a partir de emociones acumuladas y mensajes previos.
    Incluye introducción narrativa variable + inferencia por combinaciones clínicas.
    """

    if not emociones_detectadas and not mensajes:
        return ""

    # 🔁 Variantes narrativas iniciales
    introducciones = [
        "A lo largo de lo expresado, se configura un hilo emocional que podría estar atravesado por lo siguiente:",
        "En lo que expresaste, se advierte una configuración emocional que podría vincularse con:",
        "Lo mencionado permite suponer la presencia de un patrón emocional compatible con lo siguiente:"
    ]
    intro = random.choice(introducciones)

    # 🧠 Combinaciones clínicas inferenciales
    combinaciones = {
        ("insuficiencia", "rechazo", "inseguridad"): "Podría estar operando un conflicto entre la necesidad de validación y el temor a la desaprobación.",
        ("soledad", "abandono", "desesperanza"): "Se advierte una posible vivencia de carencia vincular, con tendencia al retraimiento afectivo como forma de protección.",
        ("culpa", "fracaso", "pesadez"): "Se manifiesta una lucha interna entre el ideal del yo y la percepción de fallas personales no toleradas.",
        ("apatía", "vacío", "desinterés"): "La sensación de vacío podría estar expresando una desconexión emocional como defensa frente al dolor psíquico.",
        ("enojo", "irritabilidad", "aislamiento"): "Podría tratarse de una modalidad defensiva basada en el retraimiento hostil ante frustraciones relacionales no tramitadas.",
        ("tristeza", "apatía", "desesperanza"): "Podría vincularse a una vivencia de agotamiento psíquico o desvitalización, donde el deseo y la expectativa emocional se encuentran inhibidos.",
        ("culpa", "autocrítica", "fracaso"): "Se observa un patrón de autovaloración crítica, posiblemente originando en mandatos internalizados que dificultan la autoaceptación.",
        ("ansiedad", "inseguridad"): "Podría estar manifestándose un conflicto entre la necesidad de pertenecer y el miedo a no ser valorado por el entorno.",
        ("enojo", "tristeza", "desilusión"): "Este conjunto podría estar expresando una vivencia de frustración afectiva sostenida, donde el dolor no tramitado adopta una forma reactiva.",
        ("soledad", "desconfianza", "dolor"): "Se advierte un posible retraimiento afectivo como defensa ante experiencias relacionales vividas con amenaza o ruptura."
    }

    # 🔍 Normalizar emociones
    emociones_norm = [e.lower().strip().replace(".", "") for e in emociones_detectadas]

    # 🔄 Buscar hipótesis por coincidencia
    for claves, hipotesis in combinaciones.items():
        if all(clave in emociones_norm for clave in claves):
            return f"{intro} {hipotesis}"

    # 🧠 Si no hay coincidencia clínica, usar plantilla general
    cuerpo_general = random.choice([
        "Podría tratarse de un patrón donde el deseo de ser aceptado convive con el temor profundo a la desaprobación.",
        "Se sugiere un conflicto estructural entre demandas internas y la vivencia de insuficiencia afectiva.",
        "Este relato permite entrever una vivencia que no ha sido plenamente significada, pero que resuena como una constante interna.",
        "Impresiona como una modalidad defensiva basada en el retraimiento hostil ante frustraciones relacionales no tramitadas."
    ])
    return f"{intro} {cuerpo_general}"


# ------------------------ Detección de orientación reflexiva ------------------------

def detectar_orientacion_reflexiva(mensajes: list) -> str:
    texto = " ".join(mensajes).lower()
    
    if any(palabra in texto for palabra in [
        "me doy cuenta", "a veces creo que", "entiendo que", "siento que esto viene",
        "creo que esto es por", "esto debe venir de"
    ]):
        return "insight"

    emociones_vinculo = {"rechazo", "abandono", "desaprobación", "soledad", "temor al rechazo", "desconfianza"}
    emociones_autovaloracion = {"culpa", "fracaso", "autocrítica", "insuficiencia", "inseguridad", "ansiedad"}

    emociones_detectadas = set(texto.split())

    if emociones_vinculo & emociones_detectadas:
        return "relacional"
    elif emociones_autovaloracion & emociones_detectadas:
        return "intrapersonal"
    
    return "general"
