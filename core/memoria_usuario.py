from datetime import datetime
from dateutil.relativedelta import relativedelta
from db.database import SessionLocal
from db.models import HistorialClinicoUsuario

def obtener_ultimo_historial_emocional(user_id):
    session = SessionLocal()
    try:
        return (
            session.query(HistorialClinicoUsuario)
            .filter_by(user_id=user_id)
            .order_by(HistorialClinicoUsuario.fecha.desc())
            .first()
        )
    finally:
        session.close()

def tiempo_transcurrido(desde):
    if not desde:
        return "Es la primera vez que nos contactamos."
    ahora = datetime.utcnow()
    delta = relativedelta(ahora, desde)
    partes = []
    if delta.years: partes.append(f"{delta.years} año(s)")
    if delta.months: partes.append(f"{delta.months} mes(es)")
    if delta.days: partes.append(f"{delta.days} día(s)")
    return f"Han pasado {' y '.join(partes)} desde la última vez que hablamos."

def construir_prompt_con_memoria(user_id, mensaje_usuario):
    anterior = obtener_ultimo_historial_emocional(user_id)
    tiempo_info = tiempo_transcurrido(anterior.fecha if anterior else None)
    resumen_emociones = (
        ", ".join(anterior.emociones) if anterior and anterior.emociones else "no se registraron emociones"
    )
    return [
        {"role": "system", "content": "Sos un asistente emocional con memoria del usuario."},
        {"role": "assistant", "content": f"La última vez, el usuario expresó emociones como: {resumen_emociones}. {tiempo_info}"},
        {"role": "user", "content": mensaje_usuario}
    ]
