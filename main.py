import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

from Epaper import EpaperDownloader

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
EDITION_ID = int(os.getenv("EDITION_ID", "1"))
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "./downloads"))

if not BOT_TOKEN or not CHANNEL_ID:
    raise RuntimeError("BOT_TOKEN and CHANNEL_ID must be set in .env")

IST = ZoneInfo("Asia/Kolkata")


def today_str():
    return datetime.now(IST).strftime("%d/%m/%Y")


def download_today():
    date_str = today_str()
    print(f"[INFO] Downloading newspaper for {date_str}")

    downloader = EpaperDownloader(DOWNLOAD_DIR)
    writer = downloader.download_date_pages(EDITION_ID, date_str)

    if writer is None:
        raise RuntimeError(f"Newspaper not available for {date_str}")

    month_name = datetime.now(IST).strftime("%B")
    day = datetime.now(IST).strftime("%d")
    filename = (
        f"Namaste_Telangana_{month_name}_{day}_"
        f"{date_str.replace('/', '_')}.pdf"
    )
    output = DOWNLOAD_DIR / filename

    with output.open("wb") as f:
        writer.write(f)

    if not output.exists() or output.stat().st_size == 0:
        raise RuntimeError("PDF was created but is empty")

    print(f"[OK] PDF created: {output} ({output.stat().st_size / 1024 / 1024:.2f} MB)")
    return output


def telegram_send_document(pdf_path: Path):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"

    caption = (
        f"📰 Namaste Telangana\n"
        f"📅 {datetime.now(IST).strftime('%d-%m-%Y')}"
    )

    print("[INFO] Uploading newspaper to Telegram...")

    with pdf_path.open("rb") as document:
        response = requests.post(
            url,
            data={
                "chat_id": CHANNEL_ID,
                "caption": caption,
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
            f"Telegram API error {response.status_code}: {response.text}"
        )

    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(f"Telegram rejected upload: {result}")

    print("[OK] Newspaper posted to Telegram channel.")


def already_posted(pdf_path: Path):
    marker = pdf_path.with_suffix(".posted")
    return marker.exists()


def mark_posted(pdf_path: Path):
    pdf_path.with_suffix(".posted").write_text(
        datetime.now(IST).isoformat(),
        encoding="utf-8",
    )


def run_once():
    pdf = download_today()

    if already_posted(pdf):
        print("[INFO] Today's newspaper was already posted. Skipping.")
        return

    telegram_send_document(pdf)
    mark_posted(pdf)

    print("[SUCCESS] Daily newspaper job completed.")


if __name__ == "__main__":
    try:
        run_once()
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise
