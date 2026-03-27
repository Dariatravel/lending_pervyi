# Telegram collab bot

## 1) Create virtual environment

```bash
cd "/Users/darya_botova/Documents/New project/collab_bot"
python3 -m venv .venv
source .venv/bin/activate
```

## 2) Install dependencies

```bash
pip install -r requirements.txt
```

## 3) Set environment variables

```bash
cp .env.example .env
```

Open `.env` and set:

- `BOT_TOKEN` from `@BotFather`
- `OWNER_CHAT_ID` from `@userinfobot`

## 4) Run

```bash
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
python3 bot.py
```

## 5) Test

Open your bot in Telegram, press `Start`, answer 5 questions, and check your own Telegram chat for incoming lead.

## Commands

- `/start` start form
- `/cancel` cancel form
