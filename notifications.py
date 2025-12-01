import os
import logging
from typing import Dict

import requests

# Read once at import time; environment can be updated if needed and process restarted.
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MAX_TELEGRAM_MESSAGE = 4096


def send_telegram_message(text: str) -> None:
    """Send a plain-text message to the configured Telegram chat.

    This is intentionally lightweight: it logs failures but does not raise,
    so callers (webhook handler) won't fail if Telegram is unavailable.
    """
    if not (TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
        logging.info("TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set; skipping Telegram notification.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload: Dict[str, str] = {"chat_id": TELEGRAM_CHAT_ID, "text": text}

    # Truncate message if it exceeds Telegram's maximum message length
    if len(text) > MAX_TELEGRAM_MESSAGE:
        truncated = text[: MAX_TELEGRAM_MESSAGE - 3] + "..."
        logging.info(f"Telegram message length {len(text)} exceeds {MAX_TELEGRAM_MESSAGE}, truncating to {len(truncated)} chars")
        payload["text"] = truncated

    try:
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code != 200:
            logging.warning(f"Telegram sendMessage failed: {resp.status_code} {resp.text}")
    except Exception as e:
        logging.warning(f"Telegram sendMessage error: {e}")
