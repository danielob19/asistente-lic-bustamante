import random

def seleccionar_estilo_redaccion() -> str:
    estilos = [
        "clasico",
        "inferencial",
        "estructural",
        "fenomenologico",
        "breve",
        "integrativo"
    ]
    return random.choice(estilos)

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
    else:
        return base  # fallback

def generar_hipotesis_psicodinamica(emociones_detectadas: list, mensajes: list) -> str:
    """
    Genera una hipótesis psicodinámica tentativa a partir de emociones acumuladas y mensajes previos.
    """
    if not emociones_detectadas or not mensajes:
        return ""

    combinaciones = {
        ("insuficiencia", "rechazo", "inseguridad"): (
            "Podría estar operando un conflicto entre la necesidad de validación y el temor a la desaprobación."
        ),
        ("soledad", "abandono", "desesperanza"): (
            "Se advierte una posible vivencia de carencia vincular, con tendencia al retraimiento afectivo como forma de protección."
        ),
        ("culpa", "fracaso", "ansiedad"): (
            "Es posible que se manifieste una lucha interna entre el ideal del yo y la percepción de fallas personales no toleradas."
        ),
        ("apatía", "vacío", "desinterés"): (
            "La sensación de vacío podría estar expresando una desconexión emocional como defensa frente al dolor psíquico."
        ),
        ("enojo", "irritabilidad", "aislamiento"): (
            "Podría tratarse de una modalidad defensiva basada en el retraimiento hostil ante frustraciones relacionales no tramitadas."
        ),
        ("apatía", "vacío", "desesperanza"): (
            "Podría vincularse a una vivencia de agotamiento psíquico o desvitalización, donde el deseo y la expectativa emocional se encuentran inhibidos."
        ),
        ("culpa", "autocrítica", "fracaso"): (
            "Se observa un patrón de autovaloración crítica, posiblemente originado en mandatos internalizados que dificultan la autoaceptación."
        ),
        ("temor al rechazo", "insuficiencia", "inseguridad"): (
            "Podría estar manifestándose un conflicto entre la necesidad de pertenecer y el miedo a no ser valorado por el entorno."
        ),
        ("enojo", "tristeza", "desilusión"): (
            "Este conjunto podría estar expresando una vivencia de frustración afectiva sostenida, donde el dolor no tramitado adopta una forma reactiva."
        ),
        ("soledad", "desconfianza", "dolor"): (
            "Se advierte un posible retraimiento afectivo como defensa ante experiencias relacionales vividas con amenaza o ruptura."
        ),
    }

    emociones_normalizadas = [e.lower().strip().replace(".", "") for e in emociones_detectadas]
    estilo = seleccionar_estilo_redaccion()

    for claves, hipotesis in combinaciones.items():
        if all(any(clave in emocion for emocion in emociones_normalizadas) for clave in claves):
            return reformular_hipotesis(hipotesis, estilo)

    return "Podría existir un conflicto intrapsíquico no consciente que requiere mayor exploración para ser comprendido en profundidad."
