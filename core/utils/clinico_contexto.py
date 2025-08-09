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
    conexion_pgsql=None,
) -> Optional[str]:
    """
    (Opcional) Sugiere una emoción/patrón no mencionado aún por el usuario
    a partir de combinaciones frecuentes muy simples. Si se provee una
    conexión a PostgreSQL, puede intentar un fallback por DB sin romper
    en caso de error (todo va en try/except y retorna None ante fallos).

    Devuelve:
        - str con la emoción/patrón sugerido, o
        - None si no se infiere nada.
    """
    if not emociones_detectadas:
        return None

    # Heurísticas simples por co-ocurrencia
    texto = " ".join(e.lower().strip() for e in emociones_detectadas)
    # ejemplos bien conservadores
    if re.search(r"\b(ansiedad|pánico)\b", texto) and re.search(
        r"\b(fatiga|agotamiento|insomnio)\b", texto
    ):
        return "estrés sostenido"

    if re.search(r"\b(tristeza|desgano|apatía)\b", texto) and re.search(
        r"\b(soledad|vacío)\b", texto
    ):
        return "anhedonia"

    # Fallback por DB (opcional). No es requisito tenerlo activo.
    if conexion_pgsql is not None:
        try:
            with conexion_pgsql.cursor() as cur:
                # Ejemplo genérico: buscar el estado_emocional más frecuente
                # asociado a las palabras detectadas (ajustá a tu esquema real).
                cur.execute(
                    """
                    SELECT estado_emocional, COUNT(*) AS frecuencia
                    FROM palabras_clave
                    WHERE sintoma = ANY(%s)
                    GROUP BY estado_emocional
                    ORDER BY frecuencia DESC
                    LIMIT 1
                    """,
                    (emociones_detectadas,),
                )
                row = cur.fetchone()
                if row:
                    candidato = str(row[0]).lower().strip()
                    if candidato and candidato not in {e.lower() for e in emociones_detectadas}:
                        return candidato
        except Exception as e:
            # No interrumpir el flujo clínico si la DB falla
            print(f"[clinico_contexto] Fallback por DB no disponible: {e}")

    return None
