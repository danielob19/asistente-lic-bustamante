# core/utils/tiempo.py
from datetime import datetime, timezone


def delta_preciso_desde(fecha: datetime) -> str:
    """
    Devuelve un delta humano: 'unos segundos', '5 minutos', '2 horas y 3 minutos',
    '3 días y 4 horas', '2 semanas', '5 meses', '1 año y 2 meses'.
    - Acepta datetime naive (asumido UTC) o aware (se normaliza a UTC).
    - Si la fecha está en el futuro, devuelve 'unos segundos' (ajustable).
    """
    if fecha is None:
        return "unos segundos"

    # Normalizar a UTC
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    else:
        fecha = fecha.astimezone(timezone.utc)

    ahora = datetime.now(timezone.utc)
    seg = int((ahora - fecha).total_seconds())

    # Fechas futuras: tratarlas como 'unos segundos' (o cambiar lógica a 'en X')
    if seg < 0:
        seg = 0

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
