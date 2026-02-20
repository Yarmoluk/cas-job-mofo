# Setup Guide — CAS'S JOB MOFO Bot
## Total time: ~8 minutes · Email only · No SMS needed

---

## What the Bot Does
Every morning at 7 AM, automatically:
1. Scrapes **10 job boards** — LinkedIn, Indeed CA, Glassdoor, Monster, Eluta, Talent.com, Adzuna, Job Bank Canada, ZipRecruiter, Workopolis
2. Scores each job for relevance to Cas's profile (filters junk)
3. Sends a **styled HTML email to casianglavce@gmail.com** with:
   - All new matches (with relevance stars)
   - 12 clickable live search links
   - Today's action checklist
4. Never sends the same job twice

---

## Step 1: Install Dependencies (1 min)

```bash
pip3 install requests beautifulsoup4
```

---

## Step 2: Set Up Gmail App Password (5 min)

You need a Gmail account to **send** the daily email. Use any Gmail — yours or a dedicated one.

1. Go to: https://myaccount.google.com/security
2. Enable **2-Step Verification** if not already on
3. Go to: https://myaccount.google.com/apppasswords
4. Select **"Mail"** → **"Mac"** → click **Generate**
5. Copy the 16-character password shown (looks like: `abcd efgh ijkl mnop`)

6. Open `job_scraper.py` and fill in these 3 lines in the CONFIG section:

```python
"recipient_email": "casianglavce@gmail.com",   # already set — Cas's inbox
"sender_email":    "your_gmail@gmail.com",       # the Gmail you're sending FROM
"sender_password": "abcd efgh ijkl mnop",         # the App Password from step 5
```

---

## Step 3: Test It (1 min)

```bash
cd ~/Desktop/cas-job-search/automation
python3 job_scraper.py
```

You should see:
```
🎯 CAS'S JOB MOFO — 2026-02-20 07:00
════════════════════════════════════════
  → LinkedIn: 'chief commercial officer'
  → Indeed CA: 'chief commercial officer'
  ...
📊 Results: 120 scraped → 18 qualified → 7 new today
✅ Email sent to casianglavce@gmail.com
💾 Saved: digest_20260220.html
✅ Done.
```

Check casianglavce@gmail.com — email arrives within seconds.

---

## Step 4: Automate Daily at 7 AM (1 min)

Open Terminal and run:
```bash
crontab -e
```

Add this one line (update the path to match your username):
```
0 7 * * * /usr/bin/python3 /Users/danielyarmoluk/Desktop/cas-job-search/automation/job_scraper.py >> /Users/danielyarmoluk/Desktop/cas-job-search/automation/bot.log 2>&1
```

Save and close. Done — bot runs every morning at 7 AM automatically.

To confirm it's scheduled:
```bash
crontab -l
```

---

## What Cas Gets in His Inbox Every Morning

Subject: `🎯 4 New Executive Roles — Feb 20 | CAS'S JOB MOFO`

- Styled dark-mode email
- Each job card shows: title, company, location, source board, relevance stars (⭐–⭐⭐⭐⭐⭐)
- Direct **"View Job →"** button on each card
- 12 manual search links below (one click = live search results)
- Today's action checklist at the bottom

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: bs4` | `pip3 install beautifulsoup4` |
| Email authentication failed | Must use App Password, not your real Gmail password |
| "Less secure app" error | App Password bypasses this — make sure you generated it correctly |
| No jobs found | Job sites change HTML periodically — the search links in the email still work |
| Cron not running on Mac | System Preferences → Privacy & Security → Full Disk Access → add Terminal |

---

## Also Set Up LinkedIn Job Alerts (Free, 2 min, parallel track)
These run 24/7 and land directly in Cas's inbox — set them up now:

1. Go to LinkedIn Jobs → search `"chief commercial officer" OR president Canada`
2. Click **"Set Alert"** → Daily
3. Repeat for: `VP sales industrial distribution Canada` and `CCO HVAC distribution Canada`

Done. LinkedIn emails Cas immediately when new roles match.
