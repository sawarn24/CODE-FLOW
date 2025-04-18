import os

DATABASE_URL = os.environ.get("DATABASE_URL", "dbname=code_flow user=postgres password=123456 host=localhost port=5432")
SECRET_KEY = os.environ.get("SECRET_KEY", "787045")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
