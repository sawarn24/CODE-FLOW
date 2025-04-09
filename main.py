from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI()

# Path to the public folder
public_path = Path(__file__).resolve().parent.parent / "public"

# Mount the public folder for static assets (CSS, JS, etc.)
app.mount("/public", StaticFiles(directory=public_path), name="public")

# Serve dashboard.html at root
@app.get("/", response_class=FileResponse)
async def get_dashboard():
    return FileResponse(public_path / "dashboard.html")

# Serve login.html at /login
@app.get("/login", response_class=FileResponse)
async def get_login():
    return FileResponse(public_path / "login.html")

# Serve register.html at /register
@app.get("/register", response_class=FileResponse)
async def get_register():
    return FileResponse(public_path / "register.html")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(public_path / "favicon.ico")

from fastapi import Form

# Handle POST /login
@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    # Dummy check (replace with real logic)
    if username == "admin" and password == "admin":
        return {"message": "Login successful"}
    return {"message": "Invalid credentials"}

# Handle POST /register
@app.post("/register")
async def register(username: str = Form(...), password: str = Form(...)):
    # Dummy registration logic (replace with real DB logic)
    return {"message": f"User {username} registered successfully"}
