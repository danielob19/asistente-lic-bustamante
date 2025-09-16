# core/utils/tiempo.py
from datetime import datetime, timezone

def delta_preciso_desde(fecha) -> str:
    """
    fecha: datetime naive (UTC) o aware. Devuelve '5 minutos', '2 días y 3 horas', etc.
    """
    # Normalizamos a UTC consciente
    if fecha.tzinfo is None:
        from datetime import timezone
        fecha = fecha.replace(tzinfo=timezone.utc)
    else:
        fecha = fecha.astimezone(timezone.utc)

    ahora = datetime.now(timezone.utc)
    seg = int((ahora - fecha).total_seconds())
    if seg < 45:
        return "unos segundos"
    mins = seg // 60
    if mins < 60:
        return f"{mins} minuto{'s' if mins != 1 else ''}"
    horas = mins // 60
    rem_m = mins % 60
    if horas < 24:
        return f"{horas} hora{'s' if horas != 1 else ''}" + (f" y {rem_m} minuto{'s' if rem_m != 1 else ''}" if rem_m else "")
    dias = horas // 24
    rem_h = horas % 24
    if dias < 14:
        return f"{dias} día{'s' if dias != 1 else ''}" + (f" y {rem_h} hora{'s' if rem_h != 1 else ''}" if rem_h else "")
    semanas = dias // 7
    if dias < 60:
        return f"{semanas} semana{'s' if semanas != 1 else ''}"
    meses = dias // 30
    if meses < 12:
        return f"{meses} mes{'es' if meses != 1 else ''}"
    anios = dias // 365
    rem_meses = (dias % 365) // 30
    return f"{anios} año{'s' if anios != 1 else ''}" + (f" y {rem_meses} mes{'es' if rem_meses != 1 else ''}" if rem_meses else "")
