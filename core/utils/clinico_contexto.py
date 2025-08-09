# core/utils/clinico_contexto.py

from typing import List, Optional
import re

# La sesión viva de cada usuario se guarda en memoria
# (el mismo objeto que usa routes/asistente.py)
from core.contexto import user_sessions


def hay_contexto_clinico_anterior(user_id: str) -> bool:
    """
    Devuelve True si en la sesión del usuario ya hay emociones detectadas.
    Se considera que existe 'contexto clínico previo' con al menos 1 emoción.

    Nota: esta firma (solo user_id) es la que usa asistente.py.
    """
    session = user_sessions.get(user_id)
    if not session:
        return False
    return len(session.get("emociones_detectadas", [])) >= 1


def inferir_emocion_no_dicha(
    emociones_detectadas: List[str],
    conexion_pgsql=None,  # mantenido solo por compatibilidad; no se usa
) -> Optional[str]:
    """
    Sugiere una emoción/patrón no mencionado aún por el usuario a partir de
    co-ocurrencias MUY conservadoras sobre las emociones acumuladas en sesión.

    Devuelve:
        - str con la emoción/patrón sugerido, o
        - None si no se infiere nada.
    """
    if not emociones_detectadas:
        return None

    # Heurísticas simples por co-ocurrencia (sin acceso a DB)
    texto = " ".join(e.lower().strip() for e in emociones_detectadas)

    # Ansiedad + síntomas somáticos de activación → estrés sostenido
    if re.search(r"\b(ansiedad|pánico)\b", texto) and re.search(
        r"\b(fatiga|agotamiento|insomnio)\b", texto
    ):
        return "estrés sostenido"

    # Tristeza/apatía + soledad/vacío → anhedonia
    if re.search(r"\b(tristeza|desgano|apatía)\b", texto) and re.search(
        r"\b(soledad|vacío)\b", texto
    ):
        return "anhedonia"

    # Sin inferencia adicional
    return None
