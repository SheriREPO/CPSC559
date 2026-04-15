# tasks.py — real task implementations for each worker task type

import asyncio
import base64
import io
import json
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── Config from env ───────────────────────────────────────────────────────────
GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_PASS = os.environ.get("GMAIL_PASS", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_TEXT_MODEL = "llama-3.1-8b-instant"
GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


# ── Groq API helper ───────────────────────────────────────────────────────────
async def groq_chat(messages: list, model: str = GROQ_TEXT_MODEL) -> str:
    """Call Groq using the official SDK (avoids Cloudflare bot blocking)."""
    from groq import Groq
    loop = asyncio.get_event_loop()

    def do_request():
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=512,
        )
        return response.choices[0].message.content.strip()

    return await loop.run_in_executor(None, do_request)


# ── Task 1: Image resizing/compression ───────────────────────────────────────
async def task_image_resize(details: dict) -> dict:
    try:
        from PIL import Image

        image_data = details.get("image", {})
        b64 = image_data.get("base64")
        filename = image_data.get("filename", "image.jpg")

        if not b64:
            return {"success": False, "error": "No image provided"}

        # Decode base64 → PIL image
        raw = base64.b64decode(b64)
        img = Image.open(io.BytesIO(raw))
        original_size = img.size

        # Resize to max 800x800 preserving aspect ratio
        img.thumbnail((800, 800), Image.LANCZOS)
        new_size = img.size

        # Compress and re-encode as base64
        output = io.BytesIO()
        fmt = "JPEG" if filename.lower().endswith((".jpg", ".jpeg")) else "PNG"
        img.save(output, format=fmt, quality=75, optimize=True)
        output.seek(0)
        result_b64 = base64.b64encode(output.read()).decode()

        return {
            "success": True,
            "original_size": f"{original_size[0]}x{original_size[1]}",
            "new_size": f"{new_size[0]}x{new_size[1]}",
            "format": fmt,
            "result_image": result_b64,
            "filename": filename,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Task 2: Send email ────────────────────────────────────────────────────────
async def task_send_email(details: dict) -> dict:
    try:
        recipient = details.get("recipient", "").strip()
        subject   = details.get("subject", "Message from DISTASK").strip()
        message   = details.get("message", "").strip()

        if not recipient:
            return {"success": False, "error": "No recipient provided"}
        if not GMAIL_USER or not GMAIL_PASS:
            return {"success": False, "error": "GMAIL_USER or GMAIL_PASS not configured"}

        msg = MIMEMultipart()
        msg["From"]    = GMAIL_USER
        msg["To"]      = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(message, "plain"))

        loop = asyncio.get_event_loop()
        def send():
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(GMAIL_USER, GMAIL_PASS)
                server.send_message(msg)

        await loop.run_in_executor(None, send)
        return {"success": True, "sent_to": recipient, "subject": subject}

    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Task 3: Push notification (simulated) ────────────────────────────────────
async def task_push_notification(details: dict) -> dict:
    topic   = details.get("topic", "unknown").strip()
    message = details.get("message", "").strip()

    # Simulated — in production you'd call FCM, APNs, etc.
    await asyncio.sleep(0.5)
    return {
        "success": True,
        "simulated": True,
        "topic": topic,
        "message": message,
        "note": "Push notification simulated — integrate FCM/APNs for real delivery",
    }


# ── Task 4: Sentiment analysis ────────────────────────────────────────────────
async def task_sentiment_analysis(details: dict) -> dict:
    try:
        text = details.get("text", "").strip()
        if not text:
            return {"success": False, "error": "No text provided"}
        if not GROQ_API_KEY:
            return {"success": False, "error": "GROQ_API_KEY not configured"}

        response = await groq_chat([
            {
                "role": "system",
                "content": (
                    "You are a sentiment analysis engine. "
                    "Respond ONLY with a JSON object with these fields: "
                    "sentiment (positive/negative/neutral), "
                    "confidence (0.0-1.0), "
                    "reasoning (one sentence). "
                    "No markdown, no extra text."
                ),
            },
            {"role": "user", "content": f"Analyse the sentiment of this text:\n\n{text}"},
        ])

        # Parse JSON response
        result = json.loads(response)
        return {"success": True, **result}

    except json.JSONDecodeError:
        return {"success": True, "sentiment": response, "raw": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Task 5: Image classification ─────────────────────────────────────────────
async def task_image_classification(details: dict) -> dict:
    try:
        image_data = details.get("image", {})
        b64 = image_data.get("base64")
        filename = image_data.get("filename", "image")

        if not b64:
            return {"success": False, "error": "No image provided"}
        if not GROQ_API_KEY:
            return {"success": False, "error": "GROQ_API_KEY not configured"}

        response = await groq_chat(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                        },
                        {
                            "type": "text",
                            "text": (
                                "Classify this image. Respond ONLY with a JSON object with: "
                                "category (main category), "
                                "labels (array of 3 descriptive tags), "
                                "confidence (0.0-1.0). "
                                "No markdown, no extra text."
                            ),
                        },
                    ],
                }
            ],
            model=GROQ_VISION_MODEL,
        )

        result = json.loads(response)
        return {"success": True, "filename": filename, **result}

    except json.JSONDecodeError:
        return {"success": True, "classification": response, "raw": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Task 6: Generate summary ──────────────────────────────────────────────────
async def task_generate_summary(details: dict) -> dict:
    try:
        text = details.get("text", "").strip()
        if not text:
            return {"success": False, "error": "No text provided"}
        if not GROQ_API_KEY:
            return {"success": False, "error": "GROQ_API_KEY not configured"}

        response = await groq_chat([
            {
                "role": "system",
                "content": (
                    "You are a summarisation engine. "
                    "Respond ONLY with a JSON object with these fields: "
                    "summary (2-3 sentence summary), "
                    "key_points (array of up to 4 bullet points), "
                    "word_count (integer, word count of original text). "
                    "No markdown, no extra text."
                ),
            },
            {"role": "user", "content": f"Summarise this text:\n\n{text}"},
        ])
        # Simulate longer processing time for LLM tasks
        # await asyncio.sleep(30)
        result = json.loads(response)
        return {"success": True, **result}

    except json.JSONDecodeError:
        return {"success": True, "summary": response, "raw": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Task dispatcher ───────────────────────────────────────────────────────────
TASK_HANDLERS = {
    "Image resizing/compression":           task_image_resize,
    "Send emails":                          task_send_email,
    "Push notifications":                   task_push_notification,
    "Running sentiment analysis on text":   task_sentiment_analysis,
    "Image classification":                 task_image_classification,
    "Generating summaries using an LLM API": task_generate_summary,
}

async def execute_task(task_name: str, details: dict) -> dict:
    """Route a task to its handler. Returns a result dict."""
    handler = TASK_HANDLERS.get(task_name)
    if not handler:
        return {"success": False, "error": f"Unknown task: {task_name}"}
    return await handler(details)