# core/utils/motor_fallback.py
# Motor clínico determinístico para fallback/local inference (sin OpenAI).
# Usa tablas: sintomas(id, nombre, variantes[]), cuadros(id, nombre), cuadro_sintoma(cuadro_id, sintoma_id, peso)

import re
from typing import List, Dict, Tuple

def _norm(t: str) -> str:
    t = t.lower().strip()
    t = re.sub(r"[^\w\sáéíóúüñ]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t

def detectar_sintomas_db(conn, texto: str) -> List[Dict]:
    """
    Devuelve [{'sintoma_id':..., 'nombre':..., 'match':...}, ...]
    Matchea por inclusión simple contra sintomas.variantes (TEXT[]).
    """
    cur = conn.cursor()
    cur.execute("SELECT id, nombre, variantes FROM sintomas;")
    tnorm = _norm(texto)
    hallados = []
    for sid, nombre, variantes in cur.fetchall():
        for v in (variantes or []):
            vn = _norm(v)
            if vn and vn in tnorm:
                hallados.append({"sintoma_id": sid, "nombre": nombre, "match": v})
                break
    cur.close()
    return hallados

def inferir_cuadros(conn, sintomas_detectados: List[Dict]) -> List[Tuple[str, float, List[str]]]:
    """
    Suma pesos por cuadro. Devuelve [(cuadro, score, [sintomas_aporte]), ...] desc.
    """
    if not sintomas_detectados:
        return []
    ids = [s["sintoma_id"] for s in sintomas_detectados]
    cur = conn.cursor()
    cur.execute("""
        SELECT c.nombre, s.nombre, cs.peso
        FROM cuadro_sintoma cs
        JOIN cuadros c ON c.id = cs.cuadro_id
        JOIN sintomas s ON s.id = cs.sintoma_id
        WHERE cs.sintoma_id = ANY(%s);
    """, (ids,))
    scores, detalles = {}, {}
    for cuadro, sintoma_nombre, peso in cur.fetchall():
        scores[cuadro] = scores.get(cuadro, 0.0) + float(peso or 1.0)
        detalles.setdefault(cuadro, []).append(sintoma_nombre)
    cur.close()
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [(c, sc, detalles.get(c, [])) for c, sc in ranked]

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
