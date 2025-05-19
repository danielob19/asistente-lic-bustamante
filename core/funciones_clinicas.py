# core/funciones_clinicas.py

def hay_contexto_clinico_anterior(user_id: str, contador: int, sesiones: dict) -> bool:
    """
    Evalúa si existe contexto clínico previo para un usuario determinado.
    Retorna True si el usuario ya tiene emociones registradas y el contador es mayor o igual a 6.
    """
    if user_id not in sesiones:
        return False
    if contador < 6:
        return False
    return bool(sesiones[user_id].get("emociones_detectadas"))
