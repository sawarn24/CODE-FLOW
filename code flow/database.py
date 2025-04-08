import os
import psycopg2
from psycopg2.extras import RealDictCursor
from config import DATABASE_URL

def get_db_connection():
    try:
        if os.environ.get("DATABASE_URL", "").startswith("postgres://"):
            database_url = os.environ.get("DATABASE_URL").replace("postgres://", "postgresql://")
            conn = psycopg2.connect(database_url, sslmode='require', cursor_factory=RealDictCursor)
        else:
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

        conn.autocommit = False
        print("Database connected successfully!")
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        raise e
