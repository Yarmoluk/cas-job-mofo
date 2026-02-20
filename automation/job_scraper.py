#!/usr/bin/env python3
"""
CAS'S JOB MOFO — Daily Executive Job Alert Bot
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Scrapes 10+ job boards · Scores matches · Sends SMS to Cas · Sends email digest

Setup (10 min):
  pip install requests beautifulsoup4 twilio
  Fill in CONFIG section below
  Run: python3 job_scraper.py
  Automate: crontab -e → 0 7 * * * /usr/bin/python3 /path/to/job_scraper.py
"""

import json, time, smtplib, hashlib, re, os
import requests
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from urllib.parse import quote_plus

# ════════════════════════════════════════════
#  CONFIG — Fill these in before running
# ════════════════════════════════════════════

CONFIG = {
    # ── Email ──────────────────────────────
    "recipient_email":   "casianglavce@gmail.com",   # Cas's email — already set
    "sender_email":      "daniel.yarmoluk@gmail.com",
    "sender_password":   "muec pczn gzil soxm",

    # ── Bot settings ──────────────────────
    "seen_jobs_file": "seen_jobs.json",
    "min_score":      3,                              # Min relevance score (1–5) to include
    "max_results_per_source": 15,                     # Jobs per site per query
}

# ════════════════════════════════════════════
#  SEARCH PARAMETERS
# ════════════════════════════════════════════

QUERIES = [
    "chief commercial officer",
    "chief revenue officer",
    "VP sales industrial distribution",
    "VP sales HVAC",
    "president distribution Canada",
    "CCO industrial distribution",
    "president building materials",
    "VP sales capital equipment",
    "CCO renewable energy Canada",
    "VP sales circular economy",
]

LOCATIONS_CA = ["Toronto, Ontario", "Ontario, Canada", "Canada"]
LOCATIONS_US = ["United States"]   # for remote-only US searches

HIGH_VALUE_KW = [
    "industrial", "distribution", "hvac", "building materials", "capital equipment",
    "renewable energy", "circular economy", "sustainability", "p&l", "revenue growth",
    "national", "commercial", "distributor", "cco", "cro", "president",
    "chief commercial", "chief revenue", "supply chain", "$100m", "100 million",
]

DISQUALIFY_KW = [
    "entry level", "junior", "coordinator", "intern", "student", "part-time",
    "temporary", "contract", "manager", "specialist", "analyst", "associate",
]

SENIORITY_KW = [
    "president", "chief commercial", "chief revenue", "vice president", "vp ",
    "vp,", "vp-", "general manager", "managing director", "country manager",
    "executive director", "cco", "cro", "c-suite",
]

# ════════════════════════════════════════════
#  SCRAPERS — 10 Job Boards
# ════════════════════════════════════════════

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    )
}


def safe_get(url, timeout=12):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        return r if r.status_code == 200 else None
    except Exception as e:
        print(f"  ⚠ GET failed: {url[:60]}... → {e}")
        return None


def scrape_linkedin(query: str, location: str) -> list[dict]:
    jobs = []
    url = (
        f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(query)}"
        f"&location={quote_plus(location)}&f_TPR=r86400&f_E=4,5,6"
    )
    r = safe_get(url)
    if not r:
        return jobs
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "html.parser")
    for card in soup.find_all("div", class_="base-card")[:CONFIG["max_results_per_source"]]:
        try:
            title = card.find("h3", class_="base-search-card__title")
            company = card.find("h4", class_="base-search-card__subtitle")
            loc = card.find("span", class_="job-search-card__location")
            link = card.find("a", class_="base-card__full-link")
            date = card.find("time")
            if title and company:
                jobs.append({
                    "title": title.get_text(strip=True),
                    "company": company.get_text(strip=True),
                    "location": loc.get_text(strip=True) if loc else location,
                    "url": link["href"] if link else url,
                    "date_posted": date.get("datetime", "") if date else "",
                    "source": "LinkedIn",
                })
        except Exception:
            pass
    return jobs


def scrape_indeed_ca(query: str, location: str) -> list[dict]:
    jobs = []
    url = (
        f"https://ca.indeed.com/jobs?q={quote_plus(query)}"
        f"&l={quote_plus(location)}&fromage=7"
        f"&sc=0kf%3Aexplvl%28SENIOR_LEVEL%29%3B"
    )
    r = safe_get(url)
    if not r:
        return jobs
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "html.parser")
    for card in soup.find_all("div", class_="job_seen_beacon")[:CONFIG["max_results_per_source"]]:
        try:
            title = card.find("h2", class_="jobTitle")
            company = card.find("span", {"data-testid": "company-name"})
            loc = card.find("div", {"data-testid": "text-location"})
            link = card.find("a", class_="jcs-JobTitle")
            if title:
                href = link["href"] if link else ""
                job_url = ("https://ca.indeed.com" + href) if href.startswith("/") else href or url
                jobs.append({
                    "title": title.get_text(strip=True).replace("new", "").strip(),
                    "company": company.get_text(strip=True) if company else "Unknown",
                    "location": loc.get_text(strip=True) if loc else location,
                    "url": job_url,
                    "date_posted": datetime.now().strftime("%Y-%m-%d"),
                    "source": "Indeed Canada",
                })
        except Exception:
            pass
    return jobs


def scrape_monster_ca(query: str) -> list[dict]:
    jobs = []
    url = (
        f"https://www.monster.ca/jobs/search?q={quote_plus(query)}"
        f"&where=Toronto%2C-ON&cy=ca&rad=50"
    )
    r = safe_get(url)
    if not r:
        return jobs
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "html.parser")
    for card in soup.find_all("section", class_="card-content")[:CONFIG["max_results_per_source"]]:
        try:
            title = card.find("h2", class_="title")
            company = card.find("div", class_="company")
            loc = card.find("div", class_="location")
            link = card.find("a", class_="target-job-title")
            if title:
                href = link["href"] if link else ""
                jobs.append({
                    "title": title.get_text(strip=True),
                    "company": company.get_text(strip=True) if company else "Unknown",
                    "location": loc.get_text(strip=True) if loc else "Toronto, ON",
                    "url": href if href.startswith("http") else f"https://www.monster.ca{href}",
                    "date_posted": datetime.now().strftime("%Y-%m-%d"),
                    "source": "Monster CA",
                })
        except Exception:
            pass
    return jobs


def scrape_eluta(query: str) -> list[dict]:
    """Eluta.ca — aggregates Canadian job postings directly from employer websites."""
    jobs = []
    url = (
        f"https://www.eluta.ca/search?q={quote_plus(query)}"
        f"&l=Toronto%2C+Ontario"
    )
    r = safe_get(url)
    if not r:
        return jobs
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "html.parser")
    for card in soup.find_all("li", class_="result")[:CONFIG["max_results_per_source"]]:
        try:
            title = card.find("a", class_="jobtitle")
            company = card.find("span", class_="company")
            loc = card.find("span", class_="location")
            if title:
                jobs.append({
                    "title": title.get_text(strip=True),
                    "company": company.get_text(strip=True) if company else "Unknown",
                    "location": loc.get_text(strip=True) if loc else "Canada",
                    "url": "https://www.eluta.ca" + title["href"] if title.get("href", "").startswith("/") else title.get("href", url),
                    "date_posted": datetime.now().strftime("%Y-%m-%d"),
                    "source": "Eluta.ca",
                })
        except Exception:
            pass
    return jobs


def scrape_glassdoor(query: str, location: str) -> list[dict]:
    """Glassdoor Canada — includes salary estimates."""
    jobs = []
    url = (
        f"https://www.glassdoor.ca/Job/jobs.htm?suggestCount=0&suggestChosen=false"
        f"&clickSource=searchBtn&typedKeyword={quote_plus(query)}"
        f"&locT=C&locId=2278756&jobType=fulltime"
    )
    r = safe_get(url)
    if not r:
        return jobs
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "html.parser")
    for card in soup.find_all("li", {"class": re.compile("react-job-listing")})[:CONFIG["max_results_per_source"]]:
        try:
            title = card.find("a", {"data-test": "job-link"})
            company = card.find("div", {"class": re.compile("employer-name")})
            loc = card.find("span", {"class": re.compile("location")})
            salary = card.find("span", {"class": re.compile("salary")})
            if title:
                jobs.append({
                    "title": title.get_text(strip=True),
                    "company": company.get_text(strip=True) if company else "Unknown",
                    "location": loc.get_text(strip=True) if loc else location,
                    "url": "https://www.glassdoor.ca" + title["href"] if title.get("href", "").startswith("/") else title.get("href", url),
                    "date_posted": datetime.now().strftime("%Y-%m-%d"),
                    "source": "Glassdoor CA",
                    "salary_hint": salary.get_text(strip=True) if salary else "",
                })
        except Exception:
            pass
    return jobs


def scrape_jobbank(query: str) -> list[dict]:
    """Government of Canada Job Bank — official postings, often PE/large corp."""
    jobs = []
    url = (
        f"https://www.jobbank.gc.ca/jobsearch/jobsearch"
        f"?searchstring={quote_plus(query)}&locationstring=Toronto&sort=M"
    )
    r = safe_get(url)
    if not r:
        return jobs
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "html.parser")
    for card in soup.find_all("article", class_="resultJobItem")[:CONFIG["max_results_per_source"]]:
        try:
            title = card.find("span", class_="noctitle")
            company = card.find("li", class_="business")
            loc = card.find("li", class_="location")
            link = card.find("a")
            if title:
                href = link["href"] if link else ""
                jobs.append({
                    "title": title.get_text(strip=True),
                    "company": company.get_text(strip=True) if company else "Unknown",
                    "location": loc.get_text(strip=True) if loc else "Canada",
                    "url": f"https://www.jobbank.gc.ca{href}" if href.startswith("/") else href or url,
                    "date_posted": datetime.now().strftime("%Y-%m-%d"),
                    "source": "Job Bank Canada",
                })
        except Exception:
            pass
    return jobs


def scrape_ziprecruiter(query: str) -> list[dict]:
    """ZipRecruiter Canada — growing executive board."""
    jobs = []
    url = (
        f"https://www.ziprecruiter.com/jobs-search"
        f"?search={quote_plus(query)}&location=Toronto%2C+Ontario%2C+Canada"
        f"&days=7"
    )
    r = safe_get(url)
    if not r:
        return jobs
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "html.parser")
    for card in soup.find_all("article", class_="job_result")[:CONFIG["max_results_per_source"]]:
        try:
            title = card.find("h2", class_="font-bold")
            company = card.find("a", {"data-testid": "job-card-employer"})
            loc = card.find("p", {"data-testid": "job-card-location"})
            link = card.find("a", {"data-testid": "job-card-title"})
            if title:
                href = link["href"] if link else ""
                jobs.append({
                    "title": title.get_text(strip=True),
                    "company": company.get_text(strip=True) if company else "Unknown",
                    "location": loc.get_text(strip=True) if loc else "Canada",
                    "url": href if href.startswith("http") else url,
                    "date_posted": datetime.now().strftime("%Y-%m-%d"),
                    "source": "ZipRecruiter",
                })
        except Exception:
            pass
    return jobs


def scrape_talent_com(query: str) -> list[dict]:
    """Talent.com (formerly Neuvoo) — largest Canadian job aggregator."""
    jobs = []
    url = (
        f"https://ca.talent.com/jobs?k={quote_plus(query)}"
        f"&l=Toronto%2C+ON&radius=50&bid=1"
    )
    r = safe_get(url)
    if not r:
        return jobs
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "html.parser")
    for card in soup.find_all("div", class_="card__job")[:CONFIG["max_results_per_source"]]:
        try:
            title = card.find("h2", class_="card__job-title")
            company = card.find("p", class_="card__job-empname-label")
            loc = card.find("p", class_="card__job-location")
            link = card.find("a", class_="card__job-link")
            if title:
                href = link["href"] if link else ""
                jobs.append({
                    "title": title.get_text(strip=True),
                    "company": company.get_text(strip=True) if company else "Unknown",
                    "location": loc.get_text(strip=True) if loc else "Canada",
                    "url": href if href.startswith("http") else f"https://ca.talent.com{href}",
                    "date_posted": datetime.now().strftime("%Y-%m-%d"),
                    "source": "Talent.com",
                })
        except Exception:
            pass
    return jobs


def scrape_adzuna(query: str) -> list[dict]:
    """Adzuna Canada — tech-forward job aggregator, good for senior roles."""
    jobs = []
    url = (
        f"https://www.adzuna.ca/search?q={quote_plus(query)}"
        f"&loc=Toronto&w=50&sort_by=date"
    )
    r = safe_get(url)
    if not r:
        return jobs
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "html.parser")
    for card in soup.find_all("article", class_=re.compile("a-result"))[:CONFIG["max_results_per_source"]]:
        try:
            title = card.find("h2")
            company = card.find("span", class_=re.compile("company"))
            loc = card.find("span", class_=re.compile("location"))
            link = card.find("a")
            if title:
                href = link["href"] if link else ""
                jobs.append({
                    "title": title.get_text(strip=True),
                    "company": company.get_text(strip=True) if company else "Unknown",
                    "location": loc.get_text(strip=True) if loc else "Canada",
                    "url": href if href.startswith("http") else f"https://www.adzuna.ca{href}",
                    "date_posted": datetime.now().strftime("%Y-%m-%d"),
                    "source": "Adzuna CA",
                })
        except Exception:
            pass
    return jobs


def build_search_urls() -> list[dict]:
    """Direct search URLs for manual click-through in the email/SMS digest."""
    return [
        {"label": "LinkedIn — CCO / President Canada (24h)",       "url": "https://www.linkedin.com/jobs/search/?keywords=chief+commercial+officer+OR+president&location=Canada&f_E=5,6&f_TPR=r86400"},
        {"label": "LinkedIn — VP Sales Industrial (7d)",            "url": "https://www.linkedin.com/jobs/search/?keywords=VP+sales+industrial+distribution&location=Canada&f_E=5,6&f_TPR=r604800"},
        {"label": "LinkedIn — CCO HVAC Distribution (7d)",          "url": "https://www.linkedin.com/jobs/search/?keywords=CCO+HVAC+distribution&location=Canada&f_E=5,6&f_TPR=r604800"},
        {"label": "Indeed CA — CCO / CRO Toronto (7d)",             "url": "https://ca.indeed.com/jobs?q=chief+commercial+officer+OR+chief+revenue&l=Toronto,+ON&fromage=7"},
        {"label": "Glassdoor — VP Sales Industrial Canada",         "url": "https://www.glassdoor.ca/Job/vp-sales-industrial-jobs-SRCH_KO0,20.htm?locId=2278756"},
        {"label": "ExecuNet — CCO Industrial",                      "url": "https://www.execunet.com/jobs/?q=chief+commercial+officer+industrial"},
        {"label": "Talent.com — President Distribution Canada",     "url": "https://ca.talent.com/jobs?k=president+distribution&l=Toronto"},
        {"label": "Adzuna CA — VP Sales",                           "url": "https://www.adzuna.ca/search?q=VP+sales+industrial&loc=Canada"},
        {"label": "Google Jobs — President CCO Distribution (week)","url": "https://www.google.com/search?q=%22chief+commercial%22+OR+%22VP+sales%22+industrial+distribution+Canada&ibp=htl;jobs&tbs=qdr:w"},
        {"label": "Google Jobs — CCO Renewables Canada (week)",     "url": "https://www.google.com/search?q=%22chief+commercial%22+OR+%22CCO%22+%22renewable+energy%22+Canada&ibp=htl;jobs&tbs=qdr:w"},
        {"label": "Monster CA — VP Sales Distribution",             "url": "https://www.monster.ca/jobs/search?q=VP+sales+distribution&where=Toronto%2C+ON"},
        {"label": "Workopolis — CCO / CRO Toronto",                 "url": "https://www.workopolis.com/jobsearch/find-jobs?ak=chief+commercial+officer+OR+chief+revenue&l=Toronto%2C+ON"},
    ]


# ════════════════════════════════════════════
#  SCORING & DEDUPLICATION
# ════════════════════════════════════════════

def score_job(job: dict) -> int:
    text = f"{job['title']} {job.get('description','')} {job.get('company','')}".lower()
    if any(d in text for d in DISQUALIFY_KW):
        return 0
    if not any(s in text for s in SENIORITY_KW):
        return 0
    score = 1
    hits = sum(1 for kw in HIGH_VALUE_KW if kw in text)
    score += min(3, hits // 2)
    loc = job.get("location", "").lower()
    if "toronto" in loc or "gta" in loc or "ontario" in loc:
        score = min(5, score + 1)
    elif "canada" in loc or "remote" in loc:
        score = min(5, score)
    return score


def deduplicate(jobs: list[dict]) -> list[dict]:
    seen_path = Path(CONFIG["seen_jobs_file"])
    seen = json.loads(seen_path.read_text()) if seen_path.exists() else {}
    new_jobs, updated = [], dict(seen)
    for job in jobs:
        jid = hashlib.md5(f"{job['title'].lower()}{job['company'].lower()}".encode()).hexdigest()
        if jid not in seen:
            new_jobs.append(job)
            updated[jid] = {"title": job["title"], "company": job["company"], "seen": datetime.now().isoformat()}
    seen_path.write_text(json.dumps(updated, indent=2))
    return new_jobs




# ════════════════════════════════════════════
#  EMAIL DIGEST
# ════════════════════════════════════════════

def build_email(new_jobs: list[dict], search_urls: list[dict]) -> str:
    today = datetime.now().strftime("%B %d, %Y")
    cards = ""
    if not new_jobs:
        cards = "<p style='color:#aaa;text-align:center;padding:20px;'>No new scraped matches today. Use the search links below to check manually.</p>"
    else:
        for j in sorted(new_jobs, key=lambda x: -x.get("score", 0)):
            bar_color = {"5":"#00d4aa","4":"#7c3aed","3":"#f5a623"}.get(str(j.get("score",1)),"#666")
            stars = "⭐" * j.get("score", 1)
            salary = f"<span style='background:#2a1a4a;color:#a78bfa;padding:2px 8px;border-radius:10px;font-size:11px;margin-left:6px;'>{j['salary_hint']}</span>" if j.get("salary_hint") else ""
            cards += f"""
            <div style="background:#1a1a28;border-left:4px solid {bar_color};border-radius:8px;padding:16px;margin-bottom:12px;">
              <div style="font-size:16px;font-weight:700;color:#f0f0ff;">{j['title']}</div>
              <div style="color:#8888aa;font-size:13px;margin:4px 0;">
                <strong style="color:#ccc;">{j['company']}</strong> · {j['location']} · {j['source']}{salary}
              </div>
              <div style="margin:4px 0;font-size:12px;color:#666;">
                Posted: {j.get('date_posted','Today')} · Relevance: {stars}
              </div>
              <a href="{j['url']}" style="display:inline-block;margin-top:10px;background:{bar_color};color:#0a0a0f;padding:7px 18px;border-radius:6px;font-weight:800;font-size:13px;text-decoration:none;">
                View Job →
              </a>
            </div>"""

    link_rows = ""
    for s in search_urls:
        link_rows += f"""
        <tr>
          <td style="padding:10px 14px;border-bottom:1px solid #1a1a28;">
            <a href="{s['url']}" style="color:#7c3aed;text-decoration:none;font-size:13px;font-weight:600;">{s['label']}</a>
          </td>
          <td style="padding:10px 14px;border-bottom:1px solid #1a1a28;text-align:right;">
            <a href="{s['url']}" style="background:#2a1a4a;color:#a78bfa;padding:5px 14px;border-radius:20px;font-size:12px;text-decoration:none;font-weight:700;">Search →</a>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="background:#0a0a0f;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#f0f0ff;margin:0;padding:0;">
<div style="max-width:680px;margin:0 auto;">

  <div style="background:linear-gradient(135deg,#1a0a30,#0a1a3f);padding:30px;text-align:center;">
    <div style="font-size:28px;font-weight:900;background:linear-gradient(135deg,#ff2d55,#ff6b35,#f5a623);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">
      🎯 CAS'S JOB MOFO
    </div>
    <div style="color:#8888aa;font-size:13px;margin-top:6px;">{today} · Daily Executive Job Intelligence</div>
    <div style="margin-top:14px;display:flex;justify-content:center;gap:10px;flex-wrap:wrap;">
      <span style="background:rgba(255,45,85,0.2);color:#ff6b6b;padding:5px 14px;border-radius:20px;font-size:12px;font-weight:700;">President · CCO · CRO · VP Sales</span>
      <span style="background:rgba(245,166,35,0.2);color:#f5a623;padding:5px 14px;border-radius:20px;font-size:12px;font-weight:700;">$300K+ Total Comp</span>
    </div>
  </div>

  <div style="background:#12121a;padding:24px;">
    <h2 style="color:#ff2d55;font-size:16px;font-weight:800;margin:0 0 16px;text-transform:uppercase;letter-spacing:1px;">
      🔥 New Matches — {len(new_jobs)} found today
    </h2>
    {cards}

    <h2 style="color:#7c3aed;font-size:16px;font-weight:800;margin:24px 0 12px;text-transform:uppercase;letter-spacing:1px;">
      🔍 Live Search Links — Click Now
    </h2>
    <table style="width:100%;border-collapse:collapse;background:#1a1a28;border-radius:10px;overflow:hidden;">
      {link_rows}
    </table>

    <div style="background:linear-gradient(135deg,rgba(255,45,85,0.1),rgba(124,58,237,0.1));border:1px solid rgba(124,58,237,0.3);border-radius:10px;padding:18px;margin-top:24px;">
      <div style="font-size:12px;font-weight:800;letter-spacing:1.5px;color:#ff2d55;text-transform:uppercase;margin-bottom:10px;">📋 Today's Actions</div>
      <ol style="color:#d0d0f0;font-size:13px;padding-left:20px;line-height:2.2;margin:0;">
        <li>Apply immediately to any ⭐⭐⭐⭐+ matches above</li>
        <li>Click 3+ search links — scan for anything posted today</li>
        <li>Send 2–3 LinkedIn connections to target company executives</li>
        <li>Follow up any application older than 3 days with no response</li>
        <li>Comment thoughtfully on 2 LinkedIn posts (visibility)</li>
      </ol>
    </div>
  </div>

  <div style="background:#0a0a0f;padding:16px;text-align:center;color:#444;font-size:11px;border-top:1px solid #1a1a28;">
    CAS'S JOB MOFO · Automated daily · {today}
  </div>
</div>
</body></html>"""


def send_email(subject: str, html: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = CONFIG["sender_email"]
    msg["To"]      = CONFIG["recipient_email"]
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(CONFIG["sender_email"], CONFIG["sender_password"])
            s.sendmail(CONFIG["sender_email"], CONFIG["recipient_email"], msg.as_string())
        print(f"✅ Email sent to {CONFIG['recipient_email']}")
    except Exception as e:
        print(f"❌ Email failed: {e}")
        print("   → Use Gmail App Password (not real password). Enable 2FA first.")


# ════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════

def main():
    print(f"\n🎯 CAS'S JOB MOFO — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    all_jobs: list[dict] = []

    # Run scrapes across 8 boards × top 4 queries
    scrapers = [
        ("LinkedIn",      lambda q, l: scrape_linkedin(q, l)),
        ("Indeed CA",     lambda q, l: scrape_indeed_ca(q, l)),
        ("Glassdoor CA",  lambda q, l: scrape_glassdoor(q, l)),
    ]
    for query in QUERIES[:5]:
        for name, fn in scrapers:
            print(f"  → {name}: '{query}'")
            jobs = fn(query, "Toronto, Ontario, Canada")
            all_jobs.extend(jobs)
            time.sleep(2)

    # Single-location scrapers (no location arg)
    for query in QUERIES[:3]:
        for name, fn in [
            ("Monster CA",    scrape_monster_ca),
            ("Eluta.ca",      scrape_eluta),
            ("Talent.com",    scrape_talent_com),
            ("Adzuna CA",     scrape_adzuna),
            ("Job Bank CA",   scrape_jobbank),
            ("ZipRecruiter",  scrape_ziprecruiter),
        ]:
            print(f"  → {name}: '{query}'")
            jobs = fn(query)
            all_jobs.extend(jobs)
            time.sleep(1.5)

    # Score all
    for j in all_jobs:
        j["score"] = score_job(j)

    qualified = [j for j in all_jobs if j.get("score", 0) >= CONFIG["min_score"]]
    new_jobs  = deduplicate(qualified)

    print(f"\n📊 Results: {len(all_jobs)} scraped → {len(qualified)} qualified → {len(new_jobs)} new today")

    search_urls = build_search_urls()
    today_str   = datetime.now().strftime("%b %d")
    subject     = (
        f"🎯 {len(new_jobs)} New Executive Roles — {today_str} | CAS'S JOB MOFO"
        if new_jobs else
        f"📋 Daily Search Links — {today_str} | CAS'S JOB MOFO"
    )

    # Send email
    html = build_email(new_jobs, search_urls)
    send_email(subject, html)

    # Save local preview
    out = f"digest_{datetime.now().strftime('%Y%m%d')}.html"
    Path(out).write_text(html)
    print(f"💾 Saved: {out}")
    print("\n✅ Done. Run again tomorrow at 7 AM.")


if __name__ == "__main__":
    main()
