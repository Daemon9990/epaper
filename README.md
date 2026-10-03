cd /opt/epaper
sed -n '1,240p' main.py# Daily Telegram Newspaper Bot

Uses the existing Epaper.py downloader to download today's Namaste Telangana
newspaper and post the PDF to a Telegram channel every day at 08:00 IST.

## VPS installation

sudo mkdir -p /opt/newspaper-telegram-bot
sudo cp -r . /opt/newspaper-telegram-bot/
cd /opt/newspaper-telegram-bot

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env
nano .env

Test:
.venv/bin/python main.py

Install systemd:
sudo cp newspaper-bot.service /etc/systemd/system/
sudo cp newspaper-bot.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now newspaper-bot.timer

Check:
systemctl list-timers newspaper-bot.timer
sudo systemctl status newspaper-bot.timer
sudo journalctl -u newspaper-bot.service -n 100 --no-pager
