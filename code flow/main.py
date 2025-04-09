from fastapi import FastAPI, HTTPException, Depends, Request, Body, Header, Form, Response, Cookie
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
                username VARCHAR(100) UNIQUE NOT NULL,
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
    allow_credentials=True,
)

app.mount("/static", StaticFiles(directory="frontend"), name="static")
templates = Jinja2Templates(directory="frontend")

class UserCreate(BaseModel):
    username: str
    password_hash: str



@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/register/")
def register_user(user: UserCreate):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = %s", (user.username,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Username already exists")

        hashed = hash_password(user.password_hash)
        cur.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (user.username, hashed))
        conn.commit()
        return {"message": "User registered successfully"}
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail="Registration failed")
    finally:
        if conn:
            conn.close()

class UserLogin(BaseModel):
    username: str
    password: str

@app.post("/login/")
def login(user: UserLogin):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, username, password_hash FROM users WHERE username = %s", (user.username,))
        db_user = cur.fetchone()

        if not db_user or not verify_password(user.password, db_user["password_hash"]):
            raise HTTPException(status_code=400, detail="Invalid username or password")

        token_data = {"sub": user.username}
        access_token = create_access_token(token_data)
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception:
        raise HTTPException(status_code=500, detail="Login failed")
    finally:
        cur.close()
        conn.close()


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request, 
    authorization: Optional[str] = Header(None),
    authorization_cookie: Optional[str] = Cookie(None, alias="Authorization")
):
    # Get token from header or cookie
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
    elif authorization_cookie and authorization_cookie.startswith("Bearer "):
        token = authorization_cookie.replace("Bearer ", "")
    
    user = None
    if token:
        try:
            user = get_current_user(token)
        except Exception as e:
            print(f"❌ Token validation error: {e}")
            pass

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name, email FROM users WHERE email = %s", (user['sub'],))
        user_details = cur.fetchone()
        
        if not user_details:
            print(f"❌ User not found in database: {user['sub']}")
            return RedirectResponse(url="/login", status_code=303)

        cur.execute("""
            SELECT id, title, type, created_date, description, progress 
            FROM projects 
            WHERE user_id = %s 
            ORDER BY created_date DESC 
            LIMIT 4
        """, (user_details["id"],))
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
        print(f"❌ Dashboard error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to load dashboard")
    finally:
        cur.close()
        conn.close()