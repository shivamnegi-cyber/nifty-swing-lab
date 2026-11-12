# Deployment guide (for beginners)

Follow top to bottom. Every command is explained. One-time setup, ~20 minutes.
Nothing here can place a real trade.

---

## Step 1 — Put the project on GitHub

1. On github.com, click **New repository**. Name it `nifty-swing-lab`, choose
   **Public** (free Pages + Actions), don't add a README. **Create repository**.
2. Upload the files. Easiest: unzip the project, then on the repo page
   **Add file → Upload files**, and drag in **all** the files and the `.github`
   folder. Commit. (If the hidden `.github` folder won't drag, create the file
   by hand: **Add file → Create new file**, name it
   `.github/workflows/cycle.yml`, paste the contents from the zip, commit.)

## Step 2 — Create your Telegram bot (gets you the reports)

1. In Telegram, search **@BotFather**, send `/newbot`, follow the prompts. It
   gives you a **bot token** that looks like `123456789:ABC...`. Copy it.
2. Send your new bot any message (say "hi") so it's allowed to message you.
3. Get your **chat id**: in Telegram, search **@userinfobot**, press Start. It
   replies with your numeric **Id**. Copy it.

## Step 3 — Add them as GitHub Secrets (never paste secrets into code)

In your repo: **Settings → Secrets and variables → Actions → New repository
secret**. Add two:

| Name | Value |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | the bot token from BotFather |
| `TELEGRAM_CHAT_ID` | the id from userinfobot |

## Step 4 — Turn on the dashboard (GitHub Pages)

**Settings → Pages → Build and deployment → Source → "GitHub Actions"**. Save.

## Step 5 — Run it once by hand to check everything

**Actions** tab → enable workflows if asked → **Trading cycle** → **Run
workflow**. Wait ~2 minutes for the green tick.

You should get a **Telegram message** (morning or evening depending on the time),
and your dashboard goes live at:

```
https://YOUR-USERNAME.github.io/nifty-swing-lab/
```

## Step 6 — Let it run on its own

Nothing more to do. From now on it runs every weekday at **09:30, 12:00, 14:00,
and 15:50 IST**, skipping NSE holidays by itself. The `records/` folder in your
repo fills with your audit trail (trades, daily P&L, state), committed
automatically after each run.

### How to verify it's working
- **Telegram:** you get a morning report (~09:30) and an evening report (~15:50)
  on trading days. A failure sends an immediate 🚨 alert.
- **Dashboard:** the Pages link updates; the live portfolio starts at ₹20,000
  and the P&L calendar gains a square each day.
- **Records:** open `records/state.json` and `records/trades.csv` in your repo —
  they update after each run. The **Actions** tab shows every run's log.

---

## Changing settings

Edit the `env:` block in `.github/workflows/cycle.yml` (e.g. add `CAPITAL: "50000"`
or `RISK_PCT: "0.015"`), or change defaults in `config.py`. Commit, and the next
run uses them. **Do not add new strategies here** — this is the paper phase.

## Going live later (Groww API) — NOT NOW

Live trading is hard-disabled. When you have a Groww API subscription and have
**personally decided** to go live, you will:
1. Wire the Groww SDK calls into `broker.py` (`LiveBroker.place_order`).
2. Add secrets `GROWW_API_KEY`, `GROWW_API_SECRET`, and
   `GROWW_LIVE_CONFIRM=I_UNDERSTAND_LIVE_TRADING_RISK`, and set `MODE=live`.
Until all of those exist, `config.is_live_allowed()` stays `False` and no real
order can be placed. (See VERIFICATION.md for what this requires.)

## Optional — a VPS instead of GitHub Actions

You do **not** need one for paper trading; GitHub Actions is free and enough.
A small VPS (e.g. a ₹400/month Ubuntu box) is only worth it once you go live and
want tighter timing. Setup on Ubuntu:

```bash
git clone https://github.com/YOUR-USERNAME/nifty-swing-lab.git
cd nifty-swing-lab
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env          # fill in Telegram token + chat id
```

Then install the included **systemd timer** (fires at the NSE trading times, in
IST, and retries a failed run) — the files are in `deploy/`:

```bash
# edit the two files first if your user isn't "ubuntu" or the path differs
sudo cp deploy/nifty-swing.service /etc/systemd/system/
sudo cp deploy/nifty-swing.timer   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nifty-swing.timer
systemctl list-timers nifty-swing.timer     # confirm it's scheduled
journalctl -u nifty-swing.service -f         # watch live logs
```

`Restart=on-failure` retries a crashed run, and each run self-heals anyway, so
the box can be left unattended. (A plain `cron` job works too if you prefer.)
