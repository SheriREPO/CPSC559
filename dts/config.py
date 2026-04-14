# config.py

# ── Network ──────────────────────────────────────────────
# Each server listens on BASE_PORT + server_id
# e.g. Server 1 → :9001, Server 2 → :9002, … Server 5 → :9005
BASE_PORT = 9000
# api.py base URL
API_BASE_URL = "http://127.0.0.1:8000"

SERVER_IDS = [1, 2, 3, 4, 5]

# ── Timing ───────────────────────────────────────────────
HEARTBEAT_INTERVAL  = 1      # seconds between leader heartbeats
HEARTBEAT_TIMEOUT   = 3      # seconds before a worker declares leader dead
WORKER_HB_INTERVAL  = 1      # seconds between worker → leader heartbeats
WORKER_HB_TIMEOUT   = 3      # seconds before leader declares worker dead
ELECTION_TIMEOUT    = 2      # seconds to wait for OK before claiming victory

# ── Tasks ────────────────────────────────────────────────
TASK_OPTIONS = [
    ("File Processing",  "Image resizing/compression"),
    ("File Processing",  "PDF generation from templates"),
    ("File Processing",  "Video thumbnail extraction"),
    ("File Processing",  "CSV parsing and validation"),
    ("File Processing",  "File format conversion (docx → pdf)"),
    ("Notification",     "Send emails (welcome, password reset, alerts)"),
    ("Notification",     "Push notifications"),
    ("Notification",     "SMS delivery"),
    ("Notification",     "Slack/Discord webhook messages"),
    ("Data Processing",  "Scraping and storing web data"),
    ("Data Processing",  "Aggregating analytics (daily reports)"),
    ("Data Processing",  "Database cleanup/archiving old records"),
    ("Data Processing",  "Syncing data between two services (CRM → spreadsheet)"),
    ("AI/ML",            "Running sentiment analysis on text"),
    ("AI/ML",            "Image classification"),
    ("AI/ML",            "Generating summaries using an LLM API"),
    ("AI/ML",            "Batch embeddings generation"),
    ("Dev/DevOps",       "Running tests on code submissions"),
    ("Dev/DevOps",       "Linting and formatting code"),
    ("Dev/DevOps",       "Sending build status notifications"),
    ("Dev/DevOps",       "Database backup jobs"),
]