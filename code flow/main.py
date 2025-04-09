from fastapi import FastAPI, HTTPException, Depends, Request, Body, Header, Form, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from contextlib import asynccontextmanager
from typing import Optional, List
import traceback
from datetime import datetime, timedelta

from database import get_db_connection
from auth import hash_password, verify_password, create_access_token, get_current_user

def create_tables():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                title VARCHAR(255) NOT NULL,
                type VARCHAR(50) NOT NULL,
                description TEXT,
                content TEXT,
                progress INTEGER DEFAULT 0,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        print("✅ Tables created successfully.")
    except Exception as e:
        print("❌ Error creating tables:", e)
    finally:
        cur.close()
        conn.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting app...")
    create_tables()
    yield
    print("🛑 Shutting down app...")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="frontend"), name="static")
templates = Jinja2Templates(directory="frontend")

class UserCreate(BaseModel):
    name: str
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class ProjectCreate(BaseModel):
    title: str
    type: str
    description: str
    content: Optional[str] = None
    progress: Optional[int] = 0

class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    progress: Optional[int] = None

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register", response_class=HTMLResponse)
async def register_form(
    request: Request,
    response: Response,
    user: UserCreate
):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM users WHERE email = %s", (user.email,))
        if cur.fetchone():
            return templates.TemplateResponse("register.html", {
                "request": request,
                "error": "Email already registered"
            })

        hashed_pw = hash_password(user.password)
        cur.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
            (user.name, user.email, hashed_pw)
        )
        conn.commit()

        token = create_access_token({"sub": user.email})
        redirect_response = RedirectResponse(url="/dashboard", status_code=303)
        redirect_response.set_cookie(key="Authorization", value=f"Bearer {token}", httponly=True)
        return redirect_response
    except Exception as e:
        conn.rollback()
        print("❌ Registration error:", e)
        print(traceback.format_exc())
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Registration failed. Please try again."
        })
    finally:
        cur.close()
        conn.close()
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, authorization: Optional[str] = Header(None)):
    if not authorization:
        authorization = request.cookies.get("Authorization")

    user = None
    if authorization and authorization.startswith("Bearer "):
        try:
            token = authorization.replace("Bearer ", "")
            user = get_current_user(token)
        except:
            pass

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name, email FROM users WHERE email = %s", (user['sub'],))
        user_details = cur.fetchone()

        cur.execute("""
            SELECT id, title, type, created_date, description, progress 
            FROM projects 
            WHERE user_id = %s 
            ORDER BY created_date DESC 
            LIMIT 4
        """, (user_details['id'],))
        user_projects = cur.fetchall()

        is_new_user = len(user_projects) == 0
        platform_stats = None
        if is_new_user:
            cur.execute("""
                SELECT 
                    COUNT(*) as total_projects,
                    COUNT(DISTINCT user_id) as total_users,
                    COALESCE(AVG(progress), 0) as avg_progress
                FROM projects
            """)
            platform_stats = cur.fetchone()

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "user": user_details,
            "projects": user_projects if user_projects else [],
            "is_new_user": is_new_user,
            "platform_stats": platform_stats if is_new_user else None
        })
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to load dashboard")
    finally:
        cur.close()
        conn.close()
