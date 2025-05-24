import random

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
        # Nuevas combinaciones propuestas
        ("apatía", "vacío", "desesperanza"): (
            "Podría vincularse a una vivencia de agotamiento psíquico o desvitalización, donde el deseo y la expectativa emocional se encuentran inhibidos."
        ),
        ("culpa", "autoexigencia", "fracaso"): (
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

    for claves, hipotesis in combinaciones.items():
        if all(any(clave in emocion for emocion in emociones_normalizadas) for clave in claves):
            return hipotesis

    return "Podría existir un conflicto intrapsíquico no consciente que requiere mayor exploración para ser comprendido en profundidad."
