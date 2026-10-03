import os
import time
import subprocess
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def seconds_until_8am():
    now = datetime.now(IST)
    target = now.replace(hour=8, minute=0, second=0, microsecond=0)

    if now >= target:
        target += timedelta(days=1)

    return (target - now).total_seconds()


while True:
    wait_seconds = seconds_until_8am()

    print(
        f"[INFO] Current IST: {datetime.now(IST):%Y-%m-%d %H:%M:%S}"
    )
    print(f"[INFO] Next newspaper run in {wait_seconds:.0f} seconds")

    time.sleep(wait_seconds)

    print("[INFO] Starting daily newspaper job...")

    result = subprocess.run(
        ["python", "main.py"],
        check=False,
    )

    if result.returncode != 0:
        print(
            f"[ERROR] Newspaper job failed with exit code "
            f"{result.returncode}"
        )

    # Prevent immediately running twice around the 8 AM boundary.
    time.sleep(60)
