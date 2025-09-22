from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3, hashlib, os, datetime, json

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "data.db")

app = FastAPI()
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# ---------------- Database ----------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists(DB_PATH):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT,
            email TEXT UNIQUE,
            password_hash TEXT,
            role TEXT
        )""")
        cur.execute("""
        CREATE TABLE feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            location TEXT,
            visit_date TEXT,
            rating INTEGER,
            category TEXT,
            comment TEXT,
            recommend TEXT,
            created_at TEXT
        )""")
        # Sample admin
        pw = hashlib.sha256("admin123".encode()).hexdigest()
        cur.execute("INSERT INTO users (fullname,email,password_hash,role) VALUES (?,?,?,?)",
                    ("Admin User","admin@example.com",pw,"admin"))
        conn.commit()
        conn.close()

@app.on_event("startup")
def startup():
    init_db()

# ---------------- Routes ----------------
@app.get("/")
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# ---------------- Tourist Register/Login ----------------
@app.get("/tourist/register")
def tourist_register_get(request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "role":"tourist"})

@app.post("/tourist/register")
def tourist_register_post(request: Request, fullname: str = Form(...), email: str = Form(...), password: str = Form(...)):
    pw = hashlib.sha256(password.encode()).hexdigest()
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (fullname,email,password_hash,role) VALUES (?,?,?,?)",
                    (fullname,email,pw,"tourist"))
        conn.commit()
    except Exception as e:
        return templates.TemplateResponse("register.html", {"request": request, "role":"tourist", "error": str(e)})
    return RedirectResponse(url="/tourist/login", status_code=303)

@app.get("/tourist/login")
def tourist_login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "role":"tourist"})

@app.post("/tourist/login")
def tourist_login_post(request: Request, email: str = Form(...), password: str = Form(...)):
    pw = hashlib.sha256(password.encode()).hexdigest()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email=? AND password_hash=? AND role=?", (email,pw,"tourist"))
    row = cur.fetchone()
    if not row:
        return templates.TemplateResponse("login.html", {"request": request, "role":"tourist", "error":"Invalid credentials"})
    return RedirectResponse(url=f"/tourist_dashboard?uid={row['id']}", status_code=303)

# ---------------- Tourist Dashboard ----------------
@app.get("/tourist_dashboard")
def tourist_dashboard(request: Request, uid: int = Query(...)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id=?", (uid,))
    user = cur.fetchone()
    if not user:
        return RedirectResponse(url="/tourist/login", status_code=303)
    cur.execute("SELECT f.*, u.fullname FROM feedback f LEFT JOIN users u ON f.user_id=u.id WHERE f.user_id=? ORDER BY f.id DESC", (uid,))
    feedbacks = cur.fetchall()
    conn.close()
    return templates.TemplateResponse("tourist_dashboard.html", {"request": request, "user": user, "feedbacks": feedbacks})

# ---------------- Submit Feedback ----------------
@app.post("/tourist/submit_feedback")
def submit_feedback(request: Request, uid: int = Form(...), location: str = Form(...), visit_date: str = Form(...),
                    rating: int = Form(...), category: str = Form(...), comment: str = Form(...), recommend: str = Form(...)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO feedback (user_id, location, visit_date, rating, category, comment, recommend, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (uid, location, visit_date, rating, category, comment, recommend, datetime.datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/tourist/analysis?uid={uid}", status_code=303)

# ---------------- Feedback Analysis ----------------
@app.get("/tourist/analysis")
def analysis_page(request: Request, uid: int = Query(...)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id=?", (uid,))
    user = cur.fetchone()
    ratings = [0,0,0,0,0]
    cur.execute("SELECT rating, COUNT(*) as cnt FROM feedback GROUP BY rating")
    for row in cur.fetchall():
        if 1 <= row["rating"] <=5:
            ratings[row["rating"]-1] = row["cnt"]
    cur.execute("SELECT COUNT(*) as total_feedback FROM feedback")
    total_feedback = cur.fetchone()["total_feedback"]
    cur.execute("SELECT AVG(rating) as avg_rating FROM feedback")
    avg_rating = cur.fetchone()["avg_rating"]
    avg_rating = round(avg_rating,2) if avg_rating else 0
    cur.execute("SELECT COUNT(DISTINCT location) as places_count FROM feedback")
    places_count = cur.fetchone()["places_count"]
    conn.close()
    return templates.TemplateResponse("analysis.html", {"request": request, "ratings": json.dumps(ratings),
                                                        "user": user, "total_feedback": total_feedback,
                                                        "avg_rating": avg_rating, "places_count": places_count})

# ---------------- Admin ----------------
@app.get("/admin/login")
def admin_login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "role":"admin"})

@app.post("/admin/login")
def admin_login_post(request: Request, email: str = Form(...), password: str = Form(...)):
    pw = hashlib.sha256(password.encode()).hexdigest()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email=? AND password_hash=? AND role=?", (email,pw,"admin"))
    row = cur.fetchone()
    if not row:
        return templates.TemplateResponse("login.html", {"request": request, "role":"admin", "error":"Invalid credentials"})
    return RedirectResponse(url="/admin/dashboard", status_code=303)

@app.get("/admin/dashboard")
def admin_dashboard(request: Request):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT f.*, u.fullname FROM feedback f LEFT JOIN users u ON f.user_id=u.id ORDER BY f.id DESC")
    feedbacks = cur.fetchall()
    conn.close()
    return templates.TemplateResponse("admin_dashboard.html", {"request": request, "feedbacks": feedbacks})

# ---------------- Admin Delete Feedback ----------------
@app.post("/admin/delete_feedback")
def admin_delete_feedback(fid: int = Form(...)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM feedback WHERE id=?", (fid,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/dashboard", status_code=303)
