import os
import time
import requests
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

from Epaper import EpaperDownloader

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
EDITION_ID = int(os.getenv("EDITION_ID", "1"))
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "./downloads"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN must be set in .env")

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
IST = ZoneInfo("Asia/Kolkata")

# Users who used /newspaper without a date
waiting_for_date = set()


def send_message(chat_id, text):
    response = requests.post(
        f"{API_URL}/sendMessage",
        data={
            "chat_id": chat_id,
            "text": text,
        },
        timeout=30,
    )

    if not response.ok:
        print(f"[ERROR] Send message failed: {response.text}")


def download_newspaper(date_str):
    print(f"[INFO] Downloading newspaper for {date_str}")

    downloader = EpaperDownloader(DOWNLOAD_DIR)

    writer = downloader.download_date_pages(
        EDITION_ID,
        date_str,
    )

    if writer is None:
        raise RuntimeError(
            f"Newspaper is not available for {date_str}"
        )

    date_obj = datetime.strptime(date_str, "%d/%m/%Y")

    filename = (
        f"Namaste_Telangana_{date_obj.strftime('%B')}_"
        f"{date_obj.strftime('%d')}_"
        f"{date_str.replace('/', '_')}.pdf"
    )

    output = DOWNLOAD_DIR / filename

    with output.open("wb") as f:
        writer.write(f)

    if not output.exists() or output.stat().st_size == 0:
        raise RuntimeError("PDF was created but is empty")

    print(
        f"[OK] PDF created: {output} "
        f"({output.stat().st_size / 1024 / 1024:.2f} MB)"
    )

    return output


def send_document(chat_id, pdf_path, date_str):
    print(f"[INFO] Sending PDF to user {chat_id}")

    with pdf_path.open("rb") as document:
        response = requests.post(
            f"{API_URL}/sendDocument",
            data={
                "chat_id": chat_id,
                "caption": (
                    "📰 Namaste Telangana\n"
                    f"📅 {date_str}"
                ),
            },
            files={
                "document": (
                    pdf_path.name,
                    document,
                    "application/pdf",
                )
            },
            timeout=300,
        )

    if not response.ok:
        raise RuntimeError(
            f"Telegram API error {response.status_code}: "
            f"{response.text}"
        )

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(
            f"Telegram rejected upload: {result}"
        )

    print("[OK] PDF sent successfully.")


def process_newspaper(chat_id, date_str):
    send_message(
        chat_id,
        f"⏳ Preparing your newspaper...\n\n"
        f"📅 Date: {date_str}\n\n"
        f"Please wait..."
    )

    try:
        pdf_path = download_newspaper(date_str)

        send_document(
            chat_id,
            pdf_path,
            date_str,
        )

    except Exception as exc:
        print(f"[ERROR] Manual download failed: {exc}")

        send_message(
            chat_id,
            "❌ Newspaper download failed.\n\n"
            f"Reason: {exc}"
        )


def handle_update(update):
    message = update.get("message")

    if not message:
        return

    text = message.get("text", "").strip()
    chat_id = message["chat"]["id"]

    # /start
    if text.startswith("/start"):
        waiting_for_date.discard(chat_id)

        send_message(
            chat_id,
            "👋 Hi! I am PVTLRTX News Paper Downloader Bot 📰\n\n"
            "I can help you download the latest newspaper.\n\n"
            "📅 Daily Newspaper\n"
            "⚡ Fast Download\n"
            "🤖 Automated Service\n\n"
            "📥 Download any newspaper:\n"
            "👉 /newspaper\n\n"
            "You can enter any available date.\n\n"
            "Example:\n"
            "👉 /newspaper 02/10/2026\n\n"
            "Use /help to see available commands."
        )

    # /help
    elif text.startswith("/help"):
        waiting_for_date.discard(chat_id)

        send_message(
            chat_id,
            "📰 PVTLRTX News Paper Bot\n\n"
            "📥 Download a newspaper for any available date.\n\n"
            "You can use either format:\n\n"
            "👉 /newspaper 02/10/2026\n\n"
            "or\n\n"
            "👉 /newspaper\n"
            "👉 02/10/2026"
        )

    # /newspaper
    elif text.startswith("/newspaper"):

        # Get everything after /newspaper
        parts = text.split(maxsplit=1)

        # One-line format:
        # /newspaper 02/10/2026
        if len(parts) == 2:
            date_str = parts[1].strip()

            try:
                date_obj = datetime.strptime(
                    date_str,
                    "%d/%m/%Y",
                )

                date_str = date_obj.strftime("%d/%m/%Y")

            except ValueError:
                send_message(
                    chat_id,
                    "❌ Invalid date format.\n\n"
                    "Use:\n"
                    "/newspaper DD/MM/YYYY\n\n"
                    "Example:\n"
                    "/newspaper 02/10/2026"
                )
                return

            process_newspaper(
                chat_id,
                date_str,
            )

        # Two-line format:
        # /newspaper
        # 02/10/2026
        else:
            waiting_for_date.add(chat_id)

            send_message(
                chat_id,
                "📅 Enter the newspaper date.\n\n"
                "Format: DD/MM/YYYY\n\n"
                "Example:\n"
                "02/10/2026"
            )

    # User sends date after /newspaper
    elif chat_id in waiting_for_date:

        try:
            date_obj = datetime.strptime(
                text,
                "%d/%m/%Y",
            )

            date_str = date_obj.strftime("%d/%m/%Y")

        except ValueError:
            send_message(
                chat_id,
                "❌ Invalid date format.\n\n"
                "Please use:\n"
                "DD/MM/YYYY\n\n"
                "Example:\n"
                "02/10/2026"
            )
            return

        waiting_for_date.discard(chat_id)

        process_newspaper(
            chat_id,
            date_str,
        )


def set_bot_commands():
    commands = [
        {
            "command": "start",
            "description": "Start the bot",
        },
        {
            "command": "newspaper",
            "description": "Download newspaper",
        },
        {
            "command": "help",
            "description": "Help",
        },
    ]

    response = requests.post(
        f"{API_URL}/setMyCommands",
        json={"commands": commands},
        timeout=30,
    )

    if response.ok:
        print("[OK] Bot commands menu configured.")
    else:
        print(
            f"[ERROR] Failed to configure commands: "
            f"{response.text}"
        )


def main():
    print(
        "[INFO] PVTLRTX News Paper Downloader Bot started."
    )

    set_bot_commands()

    offset = 0

    while True:
        try:
            response = requests.get(
                f"{API_URL}/getUpdates",
                params={
                    "offset": offset,
                    "timeout": 30,
                },
                timeout=35,
            )

            if not response.ok:
                print(
                    f"[ERROR] Telegram API: "
                    f"{response.text}"
                )
                time.sleep(5)
                continue

            data = response.json()

            if not data.get("ok"):
                print(
                    f"[ERROR] Telegram error: {data}"
                )
                time.sleep(5)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                handle_update(update)

        except requests.RequestException as exc:
            print(
                f"[ERROR] Connection error: {exc}"
            )
            time.sleep(5)

        except Exception as exc:
            print(
                f"[ERROR] Unexpected error: {exc}"
            )
            time.sleep(5)


if __name__ == "__main__":
    main()
