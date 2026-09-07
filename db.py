import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv(os.path.join(os.path.dirname(__file__), 'config', '.env'))

import psycopg2
from psycopg2.extras import RealDictCursor

# Configuración de conexión
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "memecoin")
POSTGRES_USER = os.getenv("POSTGRES_USER", "memecoin")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")


def get_conn():
    """Obtener conexión a PostgreSQL."""
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )


def get_cursor(conn=None):
    """Obtener cursor con factoría RealDictCursor."""
    c = conn or get_conn()
    return c, c.cursor(cursor_factory=RealDictCursor)
