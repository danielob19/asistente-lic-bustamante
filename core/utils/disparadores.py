# core/utils/disparadores.py
from __future__ import annotations
import re
import unicodedata
from typing import Dict, List

def _norm(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower().strip()

# Patrones amplios (sin acentos) para momentos/lugares/actividades frecuentes
MOMENTOS = [
    r"\bmaniana\b", r"\bmañana\b", r"\btarde\b", r"\bnoche\b", r"\bmadrugada\b",
    r"\bantes de dormir\b", r"\bal despertar\b", r"\bal mediod[ií]a\b",
    r"\bfines? de semana\b", r"\blunes\b", r"\bmartes\b", r"\bmiercoles\b",
    r"\bjueves\b", r"\bviernes\b", r"\bsabado\b", r"\bdoming(o|os)\b"
]
LUGARES = [
    r"\btrabajo\b", r"\boficina\b", r"\blaburo\b", r"\bcasa\b", r"\bhogar\b",
    r"\buniversidad\b", r"\bfacultad\b", r"\bescuela\b", r"\bcolegio\b",
    r"\btransporte\b", r"\bcolectivo\b", r"\bsubte\b", r"\btren\b", r"\bauto\b",
    r"\bgimnasio\b", r"\bconsultorio\b", r"\bhospital\b", r"\bcalle\b"
]
ACTIVIDADES = [
    r"\breuniones?\b", r"\bexamen(es)?\b", r"\bestu(di|d)ar\b", r"\btrabajar\b",
    r"\bmanejar\b", r"\bconducir\b", r"\bdisc?ut(ir|iendo)\b", r"\bdormir\b",
    r"\balmorz(ar|ando)\b", r"\bcenar\b", r"\bdescans(ar|o)\b"
]

# Captura genérica de frases tipo “cuando …”, “antes de …”, “después de …”, “al …”
GENERIC_CONTEXT = re.compile(
    r"\b(cuando|antes de|despues de|después de|al)\s+([^\.!\?,;]{3,80})",
    re.IGNORECASE
)

def extraer_disparadores(texto: str) -> Dict[str, List[str]]:
    """
    Devuelve disparadores detectados: {'frases': [...], 'momentos': [...], 'lugares': [...], 'actividades': [...]}
    Usa matching laxo + captura de “cuando … / antes de … / al …”.
    """
    if not texto:
        return {"frases": [], "momentos": [], "lugares": [], "actividades": []}

    raw = texto.strip()
    t = _norm(raw)

    def _collect(patterns: List[str]) -> List[str]:
        out = []
        for pat in patterns:
            m = re.search(pat, t, flags=re.IGNORECASE)
            if m:
                # devolvemos el fragmento crudo si existe en el original, si no el normalizado
                try:
                    frag = raw[m.start():m.end()]
                except Exception:
                    frag = m.group(0)
                out.append(frag.strip())
        # dedupe conservando orden
        seen = set(); uniq = []
        for x in out:
            k = _norm(x)
            if k not in seen:
                seen.add(k); uniq.append(x)
        return uniq

    momentos = _collect(MOMENTOS)
    lugares = _collect(LUGARES)
    actividades = _collect(ACTIVIDADES)

    frases = []
    for m in GENERIC_CONTEXT.finditer(raw):
        frag = (m.group(1) + " " + m.group(2)).strip()
        if 3 <= len(frag) <= 85:
            frases.append(frag)
    # dedupe
    seen = set(); frases_uniq = []
    for x in frases:
        k = _norm(x)
        if k not in seen:
            seen.add(k); frases_uniq.append(x)

    return {
        "frases": frases_uniq[:3],
        "momentos": momentos[:3],
        "lugares": lugares[:3],
        "actividades": actividades[:3],
    }

def resumir_disparadores(d: Dict[str, List[str]]) -> str:
    """
    Construye un resumen natural para usar en la respuesta (“cuando … / de noche / en la oficina…”).
    Prioriza 'frases', luego lugares/momentos/actividades.
    """
    if not d:
        return ""
    partes = []
    if d.get("frases"):
        partes.append(", ".join(d["frases"]))
    if d.get("momentos"):
        partes.append(", ".join(d["momentos"]))
    if d.get("lugares"):
        partes.append(", ".join(d["lugares"]))
    if d.get("actividades"):
        partes.append(", ".join(d["actividades"]))
    if not partes:
        return ""
    # prefijo amigable
    return "cuando sucede " + partes[0] if d.get("frases") else partes[0]
