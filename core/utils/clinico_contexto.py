# core/utils/clinico_contexto.py

import psycopg2
import re
from typing import List, Optional
from core.config.db_contexto import DATABASE_URL, user_sessions


def hay_contexto_clinico_anterior(user_id: str) -> bool:
    """
    Evalúa si ya hay emociones detectadas en la sesión del usuario.
    Se considera que hay contexto clínico previo si hay al menos una emoción registrada.
    """
    session = user_sessions.get(user_id)
    if session and session.get("emociones_detectadas"):
        return len(session["emociones_detectadas"]) >= 1
    return False


def inferir_emocion_no_dicha(emociones_detectadas: List[str], conexion_pgsql) -> Optional[str]:
    """
    Simula una inferencia clínica basada en combinaciones frecuentes.
    Sugiere una emoción no mencionada aún por el usuario, usando la base de datos como memoria clínica.
    """
    if not emociones_detectadas:
        return None

    try:
        with conexion_pgsql.cursor() as cursor:
            cursor.execute("""
                SELECT estado_emocional, COUNT(*) as frecuencia
                FROM palabras_clave
                WHERE sintoma = ANY(%s)
                GROUP BY estado_emocional
                ORDER BY frecuencia DESC
                LIMIT 1
            """, (emociones_detectadas,))
            resultado = cursor.fetchone()
            if resultado and resultado[0].lower().strip() not in emociones_detectadas:
                return resultado[0]
    except Exception as e:
        print("❌ Error en inferencia emocional:", e)

    return None
