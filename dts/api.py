# api.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import random

app = FastAPI()          # ← this line must be here

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

# ── AI/ML ──────────────────────────────────────────────
# ... rest stays the same

# ── AI/ML ──────────────────────────────────────────────

@app.post("/ai/sentiment")
async def sentiment(body: dict):
    text = body.get("text", "")
    # fake sentiment for demo — replace with real model later
    score = random.choice(["POSITIVE", "NEGATIVE", "NEUTRAL"])
    return {"label": score, "text": text}

@app.post("/ai/summarize")
async def summarize(body: dict):
    text = body.get("text", "")
    summary = text[:50] + "..." if len(text) > 50 else text
    return {"summary": summary}


# ── File Processing ────────────────────────────────────

@app.post("/file/resize")
async def resize(body: dict):
    file_url = body.get("file_url", "unknown")
    await asyncio.sleep(1)   # simulate processing time
    return {"status": "resized", "output": f"resized_{file_url}"}

@app.post("/file/convert")
async def convert(body: dict):
    filename = body.get("filename", "file.docx")
    await asyncio.sleep(1)
    return {"status": "converted", "output": filename.replace(".docx", ".pdf")}


# ── Notifications ──────────────────────────────────────

@app.post("/notify/email")
async def send_email(body: dict):
    to = body.get("email", "test@example.com")
    subject = body.get("subject", "Notification")
    return {"status": "sent", "to": to, "subject": subject}

@app.post("/notify/slack")
async def slack_webhook(body: dict):
    message = body.get("message", "")
    return {"status": "delivered", "message": message}


# ── Data Processing ────────────────────────────────────

@app.post("/data/scrape")
async def scrape(body: dict):
    url = body.get("url", "https://example.com")
    await asyncio.sleep(1)
    return {"status": "scraped", "url": url, "records": 42}

@app.post("/data/report")
async def generate_report(body: dict):
    await asyncio.sleep(1)
    return {"status": "done", "report": "analytics_2026.pdf"}


# ── Dev/DevOps ─────────────────────────────────────────

@app.post("/dev/test")
async def run_tests(body: dict):
    pr = body.get("pr", "unknown")
    await asyncio.sleep(1)
    passed = random.randint(18, 25)
    return {"status": "done", "pr": pr, "passed": passed, "failed": 0}

@app.post("/dev/lint")
async def lint_code(body: dict):
    filename = body.get("filename", "main.py")
    return {"status": "clean", "file": filename, "warnings": 0}