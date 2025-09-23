# core/db/config.py
import os
import psycopg2
from dotenv import load_dotenv

# Carga variables desde .env si existe
load_dotenv()

def get_conn():
    """
    Devuelve una conexión nueva a Postgres.
    Prioriza DATABASE_URL si está definida.
    No se conecta en tiempo de importación (evita 500 en ramas clínicas).
    """
    url = os.getenv("DATABASE_URL")
    if url:
        return psycopg2.connect(url)
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT"),
    )
