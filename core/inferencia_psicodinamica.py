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
            "Se advierte una posible vivencia de carencia vincular, con tendencia a retraimiento afectivo como forma de protección."
        ),
        ("culpa", "fracaso", "ansiedad"): (
            "Es posible que se manifieste una lucha interna entre el ideal del yo y la percepción de fallas personales no toleradas."
        ),
        ("apatía", "vacío", "desinterés"): (
            "La sensación de vacío podría estar expresando una desconexión emocional como defensa frente al dolor psíquico."
        ),
        ("enojo", "irritabilidad", "aislamiento"): (
            "Podría tratarse de una modalidad defensiva basada en el retraimiento hostil ante frustraciones relacionales no tramitadas."
        )
    }

    emociones_normalizadas = [e.lower().strip().replace(".", "") for e in emociones_detectadas]

    for claves, hipotesis in combinaciones.items():
        if all(any(clave in emocion for emocion in emociones_normalizadas) for clave in claves):
            return hipotesis

    return "Podría existir un conflicto intrapsíquico no consciente que requiere mayor exploración para ser comprendido en profundidad."
