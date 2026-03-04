RABBIT_URL = "amqp://guest:guest@localhost/"
SERVER_IDS = [1, 2, 3, 4, 5]
TASK_SUBMISSION_QUEUE = "task_submission"
WORKER_TASKS_QUEUE = "worker_tasks"
HEARTBEAT_TIMEOUT = 3
ELECTION_TIMEOUT = 2

TASK_OPTIONS = [

    ("File Processing", "Image resizing/compression"),
    ("File Processing", "PDF generation from templates"),
    ("File Processing", "Video thumbnail extraction"),
    ("File Processing", "CSV parsing and validation"),
    ("File Processing", "File format conversion (docx → pdf)"),
    ("Notification", "Send emails (welcome, password reset, alerts)"),
    ("Notification", "Push notifications"),
    ("Notification", "SMS delivery"),
    ("Notification", "Slack/Discord webhook messages"),
    ("Data Processing", "Scraping and storing web data"),
    ("Data Processing", "Aggregating analytics (daily reports)"),
    ("Data Processing", "Database cleanup/archiving old records"),
    ("Data Processing", "Syncing data between two services (CRM → spreadsheet)"),
    ("AI/ML", "Running sentiment analysis on text"),
    ("AI/ML", "Image classification"),
    ("AI/ML", "Generating summaries using an LLM API"),
    ("AI/ML", "Batch embeddings generation"),
    ("Dev/DevOps", "Running tests on code submissions"),
    ("Dev/DevOps", "Linting and formatting code"),
    ("Dev/DevOps", "Sending build status notifications"),
    ("Dev/DevOps", "Database backup jobs"),
]