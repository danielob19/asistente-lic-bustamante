import os
import psycopg2
from dotenv import load_dotenv

# Carga variables desde .env si existe
load_dotenv()

# Establecer conexión con PostgreSQL
conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    port=os.getenv("DB_PORT")
)
