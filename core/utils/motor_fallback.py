# core/utils/motor_fallback.py
# ------------------------------------------------------------
# Fallback heurístico DESACTIVADO por defecto.
# Mantiene compatibilidad para que cualquier llamada existente
# no rompa, pero en producción NO realiza inferencias clínicas.
# Si querés reactivarlo para laboratorio, poné ENABLE_FALLBACK=True.
# ------------------------------------------------------------

from __future__ import annotations
from typing import List, Tuple, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Producción: solo OpenAI. El fallback NO debe intervenir.
ENABLE_FALLBACK: bool = False

__all__ = [
    "ENABLE_FALLBACK",
    # Wrappers seguros
    "safe_detectar_sintomas",
    "safe_inferir_cuadros",
    "safe_decidir",
    # Aliases de compatibilidad (nom. legacy)
    "detectar_sintomas_db",
    "inferir_cuadros",
    "decidir",
]


# ---------------------------
# Helpers (opcionales)
# ---------------------------
def _norm_list_str(xs: Optional[List[str]]) -> List[str]:
    """Normaliza lista de strings (strip/lower) y deduplica conservando orden."""
    if not xs:
        return []
    seen, out = set(), []
    for x in xs:
        if isinstance(x, str):
            y = " ".join(x.strip().lower().split())
            if y and y not in seen:
                seen.add(y)
                out.append(y)
    return out


# ============================================================
# STUBS con guard (no-ops si ENABLE_FALLBACK=False)
# ============================================================
def detectar_sintomas_db(
    texto: Optional[str] = None,
    user_id: Optional[str] = None,
    limite: int = 5,
    *args: Any,
    **kwargs: Any
) -> List[str]:
    """
    (Fallback) Detecta síntomas usando reglas/DB.
    Producción: desactivado → devuelve [] sin hacer nada.
    Acepta parámetros opcionales para compatibilidad con llamadas antiguas.
    """
    if not ENABLE_FALLBACK:
        logger.debug("[fallback] detectar_sintomas_db desactivado → []")
        return []
    # --- Si se reactivara en laboratorio, implementar aquí la lógica real ---
    try:
        # ejemplo de retorno normalizado:
        # return _norm_list_str(heuristica(texto, ...))
        return []
    except Exception as e:
        logger.warning("[fallback] detectar_sintomas_db error: %s", e)
        return []


def inferir_cuadros(
    texto: Optional[str] = None,
    emociones: Optional[List[str]] = None,
    sintomas: Optional[List[str]] = None,
    user_id: Optional[str] = None,
    *args: Any,
    **kwargs: Any
) -> List[str]:
    """
    (Fallback) Infere cuadros a partir de síntomas/emociones/DB.
    Producción: desactivado → devuelve [].
    """
    if not ENABLE_FALLBACK:
        logger.debug("[fallback] inferir_cuadros desactivado → []")
        return []
    try:
        # return _norm_list_str(modelo_reglas(...))
        return []
    except Exception as e:
        logger.warning("[fallback] inferir_cuadros error: %s", e)
        return []


def decidir(
    emociones: Optional[List[str]] = None,
    historial: Optional[List[Any]] = None,
    global_stats: Optional[Dict[str, Any]] = None,
    umbral: int = 2,
    *args: Any,
    **kwargs: Any
) -> Tuple[bool, Optional[str], List[str]]:
    """
    (Fallback) Decide si hay suficientes coincidencias para un cuadro.
    Producción: desactivado → devuelve (False, None, []).
    Retorno: (dispara, cuadro, señales_usadas)
    """
    if not ENABLE_FALLBACK:
        logger.debug("[fallback] decidir desactivado → (False, None, [])")
        return (False, None, [])
    try:
        # return (True/False, cuadro, señales)
        return (False, None, [])
    except Exception as e:
        logger.warning("[fallback] decidir error: %s", e)
        return (False, None, [])


# ============================================================
# Wrappers SEGUROS (recomendado usarlos en el resto del código)
# Siempre devuelven valores neutros si ENABLE_FALLBACK=False.
# ============================================================
def safe_detectar_sintomas(*args: Any, **kwargs: Any) -> List[str]:
    if not ENABLE_FALLBACK:
        logger.debug("[fallback] safe_detectar_sintomas → [] (desactivado)")
        return []
    try:
        return detectar_sintomas_db(*args, **kwargs)
    except Exception as e:
        logger.warning("[fallback] detectar_sintomas_db error: %s", e)
        return []


def safe_inferir_cuadros(*args: Any, **kwargs: Any) -> List[str]:
    if not ENABLE_FALLBACK:
        logger.debug("[fallback] safe_inferir_cuadros → [] (desactivado)")
        return []
    try:
        return inferir_cuadros(*args, **kwargs)
    except Exception as e:
        logger.warning("[fallback] inferir_cuadros error: %s", e)
        return []


def safe_decidir(*args: Any, **kwargs: Any) -> Tuple[bool, Optional[str], List[str]]:
    if not ENABLE_FALLBACK:
        logger.debug("[fallback] safe_decidir → (False, None, []) (desactivado)")
        return (False, None, [])
    try:
        return decidir(*args, **kwargs)
    except Exception as e:
        logger.warning("[fallback] decidir error: %s", e)
        return (False, None, [])


# ============================================================
# Compatibilidad hacia atrás:
# Re-exportamos los WRAPPERS con los nombres legacy.
# Esto garantiza que cualquier "from ... import detectar_sintomas_db"
# termine usando el wrapper seguro (no-op en producción).
# ============================================================
detectar_sintomas_db = safe_detectar_sintomas
inferir_cuadros      = safe_inferir_cuadros
decidir              = safe_decidir
