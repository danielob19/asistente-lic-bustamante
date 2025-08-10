# core/utils/motor_fallback.py
# Motor clínico determinístico para fallback/local inference (sin OpenAI).
# Ahora todo se basa en la tabla historial_clinico_usuario.

import re
from typing import List, Dict, Tuple
import psycopg2

def _norm(t: str) -> str:
    t = t.lower().strip()
    t = re.sub(r"[^\w\sáéíóúüñ]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t

def detectar_sintomas_db(conn, user_id: str, texto: str) -> List[Dict]:
    """
    Devuelve [{'nombre':..., 'match':...}, ...]
    Matchea por inclusión simple contra historial_clinico_usuario.sintomas (TEXT[]).
    """
    cur = conn.cursor()
    # Normalizamos el texto de entrada
    tnorm = _norm(texto)

    hallados = []
    # Obtenemos todos los síntomas previos para el usuario
    cur.execute("""
        SELECT DISTINCT unnest(sintomas)
        FROM historial_clinico_usuario
        WHERE user_id = %s AND array_length(sintomas, 1) > 0;
    """, (user_id,))
    
    for (sintoma,) in cur.fetchall():
        if not sintoma:
            continue
        snorm = _norm(sintoma)
        if snorm and snorm in tnorm:
            hallados.append({"nombre": sintoma, "match": sintoma})
    
    cur.close()
    return hallados

def inferir_cuadros(conn, user_id: str) -> List[Tuple[str, float, List[str]]]:
    """
    Usa historial_clinico_usuario.cuadro_clinico_probable para inferir cuadros.
    Devuelve [(cuadro, score, [sintomas])].
    Nota: El 'score' aquí es ficticio (1.0) ya que no hay ponderación.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT cuadro_clinico_probable, sintomas
        FROM historial_clinico_usuario
        WHERE user_id = %s AND cuadro_clinico_probable IS NOT NULL
        ORDER BY fecha DESC
        LIMIT 10;
    """, (user_id,))
    
    cuadros_map = {}
    for cuadro, sintomas in cur.fetchall():
        if not cuadro:
            continue
        cuadros_map.setdefault(cuadro, {"score": 0.0, "sintomas": set()})
        cuadros_map[cuadro]["score"] += 1.0
        if sintomas:
            cuadros_map[cuadro]["sintomas"].update(sintomas)

    cur.close()
    # Convertir a lista ordenada por score
    ranked = sorted(
        [(c, data["score"], list(data["sintomas"])) for c, data in cuadros_map.items()],
        key=lambda x: x[1],
        reverse=True
    )
    return ranked

def decidir(db_rank: List[Tuple[str, float, List[str]]], umbral_coincidencias:int=2):
    """
    Evidencia suficiente = >= umbral_coincidencias síntomas distintos asociados al top-cuadro.
    """
    if not db_rank:
        return (False, None, [])
    cuadro, score, lista = db_rank[0]
    sintomas_unicos = list(sorted(set(lista)))
    if len(sintomas_unicos) >= umbral_coincidencias:
        return (True, cuadro, sintomas_unicos)
    return (False, cuadro, sintomas_unicos)
