# core/config/db_contexto.py

import os
from sqlalchemy import create_engine

# Obtener la URL de la base de datos desde las variables de entorno de Render
DATABASE_URL = os.environ["DATABASE_URL"]

# Crear engine global de SQLAlchemy para conexiones
engine = create_engine(DATABASE_URL)

# Sesiones activas en memoria
user_sessions = {}
