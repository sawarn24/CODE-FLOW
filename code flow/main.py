from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from contextlib import asynccontextmanager
from typing import Optional
import traceback

from database import get_db_connection
from auth import hash_password, verify_password, create_access_token, get_current_user




def create_tables():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                fullname VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(50) DEFAULT 'user'
            )
        """)
        conn.commit()
        print(" Tables created successfully.")
    except Exception as e:
        print(" Error creating tables:", e)
    finally:
        cur.close()
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting app...")
    create_tables()
    yield
    print(" Shutting down app...")

app = FastAPI(lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount("/static", StaticFiles(directory="frontend"), name="static")
templates = Jinja2Templates(directory="frontend")




@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})



class UserCreate(BaseModel):
    fullname: str
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str



@app.post("/register/")
def register_user(user: UserCreate):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM users WHERE email = %s", (user.email,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Email already registered")

        hashed_pw = hash_password(user.password)
        cur.execute(
            "INSERT INTO users (fullname, email, password_hash) VALUES (%s, %s, %s)",
            (user.fullname, user.email, hashed_pw)
        )
        conn.commit()
        return {"message": "User registered successfully"}
    except Exception as e:
        conn.rollback()
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Registration failed")
    finally:
        cur.close()
        conn.close()


@app.post("/login/")
def login_user(user: UserLogin):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, fullname, email, password_hash, role FROM users WHERE email = %s", (user.email,))
        db_user = cur.fetchone()
        if not db_user or not verify_password(user.password, db_user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token = create_access_token({"sub": db_user["email"], "role": db_user["role"]})
        return {"access_token": token, "token_type": "bearer"}
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Login failed")
    finally:
        cur.close()
        conn.close()



@app.get("/profile/")
def get_profile(user: dict = Depends(get_current_user)):
    return {"message": f"Welcome, {user['sub']}! Role: {user['role']}"}
