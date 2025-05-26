import re

def detectar_intencion_bifurcada(mensaje: str) -> dict:
    mensaje = mensaje.lower()

    # Patrones para detectar intención clínica
    patrones_clinicos = [
        r"\b(triste|deprimido|ansioso|estresado|miedo|fobia|ansiedad|depresión|pánico)\b",
        r"no\s+puedo\s+más",
        r"me\s+siento\s+mal",
        r"no\s+quiero\s+vivir",
        r"estoy\s+agotado",
        r"me\s+cuesta\s+todo",
    ]

    # Patrones para detectar intención administrativa
    patrones_administrativos = [
        r"\b(costo|precio|cuánto\s+cuesta|modalidad|horarios|dónde\s+atiende|cómo\s+se\s+paga|turno|agenda|disponibilidad)\b",
        r"\b(atienden|tratan|realizan)\b.*\b(depresión|fobia|ansiedad|terapia|tratamiento)\b",
        r"\b(quiero|necesito|busco|estoy\s+buscando)\b.*\b(terapia|psicoterapia|tratamiento)\b",
    ]

    es_clinico = any(re.search(patron, mensaje) for patron in patrones_clinicos)
    es_administrativo = any(re.search(patron, mensaje) for patron in patrones_administrativos)

    if es_clinico and es_administrativo:
        return {"intencion": "MIXTA"}
    elif es_clinico:
        return {"intencion": "CLINICA"}
    elif es_administrativo:
        return {"intencion": "ADMINISTRATIVA"}
    else:
        return {"intencion": "INDEFINIDA"}
