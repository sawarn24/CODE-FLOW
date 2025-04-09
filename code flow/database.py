import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "postgres")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "123456")  # Replace with actual password

DATABASE_URL = os.environ.get("DATABASE_URL") or f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def get_db_connection():
    try:
       
        if DATABASE_URL.startswith("postgres://"):
            connection_string = DATABASE_URL.replace("postgres://", "postgresql://")
        else:
            connection_string = DATABASE_URL
            
        
        conn = psycopg2.connect(connection_string, cursor_factory=RealDictCursor)
        conn.autocommit = False
        print("Database connected successfully!")
        return conn
    except psycopg2.OperationalError as e:
        print(f"Database connection error: {e}")
        print(f"Failed to connect to {DB_HOST}:{DB_PORT} as user '{DB_USER}'")
        print("Please check your database credentials and ensure PostgreSQL is running.")
        raise e
    except Exception as e:
        print(f"Unexpected error connecting to database: {e}")
        raise e