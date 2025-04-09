from fastapi import FastAPI, HTTPException, Depends, Request, Body, Header
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

# ========== DATABASE TABLE CREATION ==========

def create_tables():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Users table - simplified schema
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL
            )
        """)
        
        # Projects table
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

# ========== LIFESPAN EVENT HOOK ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting app...")
    create_tables()
    yield
    print("🛑 Shutting down app...")

# ========== APP INITIALIZATION ==========

app = FastAPI(lifespan=lifespan)

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static and Template Setup
app.mount("/static", StaticFiles(directory="frontend"), name="static")
templates = Jinja2Templates(directory="frontend")

# ========== MODELS ==========

# Simplified UserCreate model
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

# ========== ROUTES ==========

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

# Fixed dashboard route - combined the duplicate routes
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    authorization: Optional[str] = Header(None)
):
    # Try to get user from token in header first
    user = None
    if authorization and authorization.startswith("Bearer "):
        try:
            token = authorization.replace("Bearer ", "")
            user = get_current_user(token)
        except:
            pass
    
    # If no user, redirect to login
    if not user:
        return RedirectResponse(url="/login", status_code=303)
        
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Get user details
        cur.execute("SELECT id, name, email FROM users WHERE email = %s", (user['sub'],))
        user_details = cur.fetchone()
        
        # Get user's projects
        cur.execute("""
            SELECT id, title, type, created_date, description, progress 
            FROM projects 
            WHERE user_id = %s 
            ORDER BY created_date DESC 
            LIMIT 4
        """, (user_details['id'],))
        user_projects = cur.fetchall()
        
        # Check if user is new (no projects)
        is_new_user = len(user_projects) == 0
        
        # If new user, fetch platform statistics
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

# ========== API ROUTES ==========

# Fixed registration endpoint - added proper error handling
@app.post("/register/")
def register_user(user_data: UserCreate = Body(...)):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Check if email already exists
        cur.execute("SELECT id FROM users WHERE email = %s", (user_data.email,))
        if cur.fetchone():
            return JSONResponse(
                status_code=400,
                content={"detail": "Email already registered"}
            )

        hashed_pw = hash_password(user_data.password)
        
        # Insert user with simplified schema
        cur.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
            (user_data.name, user_data.email, hashed_pw)
        )
        user_id = cur.fetchone()['id']
        conn.commit()

        # Create token for immediate login
        token = create_access_token({"sub": user_data.email})
        
        return {
            "message": "User registered successfully",
            "user_id": user_id,
            "access_token": token,
            "token_type": "bearer"
        }
    except Exception as e:
        conn.rollback()
        print(f"Registration error: {str(e)}")
        print(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"detail": f"Registration failed: {str(e)}"}
        )
    finally:
        cur.close()
        conn.close()

@app.post("/login/")
def login_user(user_data: UserLogin = Body(...)):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Updated query to fetch only necessary fields
        cur.execute("SELECT id, name, email, password_hash FROM users WHERE email = %s", (user_data.email,))
        db_user = cur.fetchone()
        
        if not db_user or not verify_password(user_data.password, db_user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Create access token with just email
        token = create_access_token({"sub": db_user["email"]})
        return {"access_token": token, "token_type": "bearer"}
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Login failed")
    finally:
        cur.close()
        conn.close()

# ========== PROJECT ROUTES ==========

@app.post("/projects/")
async def create_project(project: ProjectCreate, user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Get user ID
        cur.execute("SELECT id FROM users WHERE email = %s", (user['sub'],))
        user_id = cur.fetchone()['id']
        
        # Create project
        cur.execute("""
            INSERT INTO projects (user_id, title, type, description, content, progress)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (user_id, project.title, project.type, project.description, 
              project.content, project.progress))
        
        project_id = cur.fetchone()['id']
        conn.commit()
        
        return {"message": "Project created successfully", "project_id": project_id}
    except Exception as e:
        conn.rollback()
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to create project")
    finally:
        cur.close()
        conn.close()

@app.get("/projects/")
async def get_user_projects(user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Get user ID
        cur.execute("SELECT id FROM users WHERE email = %s", (user['sub'],))
        user_id = cur.fetchone()['id']
        
        # Get user's projects
        cur.execute("""
            SELECT id, title, type, description, progress, created_date, updated_date
            FROM projects
            WHERE user_id = %s
            ORDER BY updated_date DESC
        """, (user_id,))
        
        projects = cur.fetchall()
        return {"projects": projects}
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to fetch projects")
    finally:
        cur.close()
        conn.close()

@app.get("/projects/{project_id}")
async def get_project(project_id: int, user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Get user ID
        cur.execute("SELECT id FROM users WHERE email = %s", (user['sub'],))
        user_id = cur.fetchone()['id']
        
        # Get project details
        cur.execute("""
            SELECT id, title, type, description, content, progress, created_date, updated_date
            FROM projects
            WHERE id = %s AND user_id = %s
        """, (project_id, user_id))
        
        project = cur.fetchone()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
            
        return {"project": project}
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to fetch project")
    finally:
        cur.close()
        conn.close()

@app.put("/projects/{project_id}")
async def update_project(project_id: int, project_update: ProjectUpdate, user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Get user ID
        cur.execute("SELECT id FROM users WHERE email = %s", (user['sub'],))
        user_id = cur.fetchone()['id']
        
        # Check if project exists and belongs to user
        cur.execute("SELECT id FROM projects WHERE id = %s AND user_id = %s", (project_id, user_id))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Build update query dynamically based on provided fields
        update_parts = []
        params = []
        
        if project_update.title is not None:
            update_parts.append("title = %s")
            params.append(project_update.title)
            
        if project_update.type is not None:
            update_parts.append("type = %s")
            params.append(project_update.type)
            
        if project_update.description is not None:
            update_parts.append("description = %s")
            params.append(project_update.description)
            
        if project_update.content is not None:
            update_parts.append("content = %s")
            params.append(project_update.content)
            
        if project_update.progress is not None:
            update_parts.append("progress = %s")
            params.append(project_update.progress)
        
        update_parts.append("updated_date = CURRENT_TIMESTAMP")
        
        if update_parts:
            query = f"UPDATE projects SET {', '.join(update_parts)} WHERE id = %s AND user_id = %s"
            params.extend([project_id, user_id])
            
            cur.execute(query, params)
            conn.commit()
            
            return {"message": "Project updated successfully"}
        else:
            return {"message": "No changes to update"}
    except Exception as e:
        conn.rollback()
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to update project")
    finally:
        cur.close()
        conn.close()

@app.delete("/projects/{project_id}")
async def delete_project(project_id: int, user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Get user ID
        cur.execute("SELECT id FROM users WHERE email = %s", (user['sub'],))
        user_id = cur.fetchone()['id']
        
        # Check if project exists and belongs to user
        cur.execute("SELECT id FROM projects WHERE id = %s AND user_id = %s", (project_id, user_id))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Delete project
        cur.execute("DELETE FROM projects WHERE id = %s AND user_id = %s", (project_id, user_id))
        conn.commit()
        
        return {"message": "Project deleted successfully"}
    except Exception as e:
        conn.rollback()
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to delete project")
    finally:
        cur.close()
        conn.close()