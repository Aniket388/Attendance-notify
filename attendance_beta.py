"""
Attendance bot - BETA (V11.0)

BETA LOCK: only processes BETA_USER and only ever emails BETA_RECIPIENT.

What changed vs V10.5
- Attendance table is found by HEADER NAMES (Course Name / Present Count /
  Total Count / Percentage), not by fixed column positions. Re-ordering or
  adding columns no longer breaks it.
- Only a real LoginError (bad credentials) counts toward the 3-strike
  deactivation. Site/layout problems never deactivate anyone; they email the
  owner a short diagnostic instead.
- Exit code is non-zero when something failed, so the GitHub run turns red.
- "Yesterday" uses India time (Asia/Kolkata) instead of the runner's UTC.
- Multiple fallbacks for opening the attendance page from the dashboard.
"""
import os
import re
import sys
import time
import json
import html
import base64
import argparse
import traceback
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from supabase import create_client
from cryptography.fernet import Fernet
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
BOT_VERSION = "V11.0"
LOGIN_URL = "https://nietcloud.niet.co.in/login.htm"
HOME_URL = "https://nietcloud.niet.co.in/home.htm"
IST = ZoneInfo("Asia/Kolkata")

BETA_LOCK = True                       # set False only when promoting to production
BETA_USER = "0231csiot122@niet.co.in"  # the only account this beta processes
BETA_RECIPIENT = "jainaniket388@gmail.com"  # the only address this beta emails

MAX_STRIKES = 3

# Login form selectors, tried in order (first visible match wins)
USERNAME_SELECTORS = [
    (By.ID, "j_username"),
    (By.NAME, "j_username"),
    (By.CSS_SELECTOR, "input[type='text'][name*='user' i]"),
]
PASSWORD_SELECTORS = [
    (By.ID, "password-1"),
    (By.CSS_SELECTOR, "input[type='password']"),
]
SUBMIT_SELECTORS = [
    (By.CSS_SELECTOR, "button[type='submit']"),
    (By.CSS_SELECTOR, "input[type='submit']"),
]

supabase = None
cipher = None


class LoginError(Exception):
    """Credentials rejected. The ONLY error that counts as a strike."""


class LayoutError(Exception):
    """The portal looks different from what the bot expects."""


# ----------------------------------------------------------------------------
# SETUP
# ----------------------------------------------------------------------------
def init_clients():
    global supabase, cipher
    supabase = create_client(
        os.environ.get("SUPABASE_URL", "").strip(), os.environ.get("SUPABASE_KEY", "").strip()
    )
    cipher = Fernet(os.environ.get("MASTER_KEY", "").strip().encode())


def make_driver():
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--ignore-certificate-errors")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    opts.add_argument("--disable-popup-blocking")
    opts.set_capability("unhandledPromptBehavior", "accept")
    opts.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
    })
    return webdriver.Chrome(options=opts)


# ----------------------------------------------------------------------------
# EMAIL
# ----------------------------------------------------------------------------
def send_email_via_api(target_email, subject, html_content):
    if BETA_LOCK and (target_email or "").strip().lower() != BETA_RECIPIENT:
        print(f"   🔒 BETA LOCK: refusing to email {target_email!r}")
        return False
    try:
        token = json.loads(os.environ.get("GMAIL_TOKEN_JSON", "").strip())
        creds = Credentials.from_authorized_user_info(token)
        service = build("gmail", "v1", credentials=creds)
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = "me"
        msg["To"] = target_email
        msg.attach(MIMEText(html_content, "html", "utf-8"))
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        print(f"   📧 Email sent to {target_email}")
        return True
    except Exception as e:
        print(f"   ❌ Email failed: {e}")
        return False


def notify_owner(subject, text):
    body = (
        "<div style='font-family:monospace;font-size:13px'>"
        f"<p><b>{html.escape(subject)}</b></p>"
        f"<pre style='white-space:pre-wrap'>{html.escape(text)}</pre></div>"
    )
    send_email_via_api(BETA_RECIPIENT, f"🛠️ Attendance bot: {subject}", body)


def get_personality(percentage):
    try:
        p = float(percentage)
    except (TypeError, ValueError):
        return {"quote": "Attendance Updated", "status": "View Data",
                "color": "#1976d2", "subject_icon": "📅"}
    if p >= 90:
        return {"quote": "Absolute Legend! 🏆 Basically living at college.", "status": "Safe Zone", "color": "#3A7D68", "subject_icon": "🏆"}
    elif p >= 75:
        return {"quote": "You are Safe! Keep maintaining this flow.", "status": "On Track", "color": "#3A7D68", "subject_icon": "✅"}
    elif p >= 60:
        return {"quote": "You are on thin ice! Don't skip anymore classes.", "status": "Attendance is Low", "color": "#C27C2E", "subject_icon": "⚠️"}
    else:
        return {"quote": "DANGER ZONE! Run to college immediately!", "status": "Critical Low", "color": "#B94A40", "subject_icon": "🚨"}


def build_email(overall, attended, delivered, subjects):
    """Same look as V10.5. Returns (subject_line, html_body)."""
    final_percent = "N/A" if overall is None else f"{overall}%"
    personality = get_personality(overall)

    table_html = ""
    for subj in subjects:
        if subj["total"] == 0:
            p_color, p_weight, p_txt = "#9AA0A6", "500", "–"
        else:
            p_color = "#B94A40" if subj["percent"] < 75 else "#3C4043"
            p_weight = "600" if subj["percent"] < 75 else "500"
            p_txt = f"{subj['percent']:.2f}%"

        if subj["yesterday"] == "Present":
            badge = ("<span style='background-color:#E8F3F0; color:#2E6B58; padding:6px 12px;"
                     " border-radius:16px; font-size:0.75em; font-weight:700;"
                     " letter-spacing:0.3px; text-transform:uppercase;'>Present</span>")
        elif subj["yesterday"] == "Absent":
            badge = ("<span style='background-color:#F7EBEA; color:#9E3F36; padding:6px 12px;"
                     " border-radius:16px; font-size:0.75em; font-weight:700;"
                     " letter-spacing:0.3px; text-transform:uppercase;'>Absent</span>")
        else:
            badge = "<span style='color:#9AA0A6; font-size:1.5em; line-height:0.8;'>-</span>"

        count_txt = f"{subj['present']}/{subj['total']}"
        table_html += f"""
        <tr style="border-bottom: 1px solid #F1F3F4;">
            <td style="padding: 16px 20px; font-size: 0.9em; color: #3C4043; line-height: 1.4; font-weight:500; vertical-align:middle;">{html.escape(subj['name'])}</td>
            <td style="padding: 16px 20px; text-align: right; white-space: nowrap; vertical-align:middle;">
                <div style="font-size: 1em; color: {p_color}; font-weight: {p_weight};">{p_txt}</div>
                <div style="font-size: 0.8em; color: #70757A; margin-top: 4px; font-weight: 500;">{count_txt}</div>
            </td>
            <td style="padding: 16px 20px; text-align: right; white-space: nowrap; width: 90px; vertical-align:middle;">
                {badge}
            </td>
        </tr>
        """

    subject_line = f"{personality['subject_icon']} {personality['status']}: {final_percent}"
    html_body = f"""
    <div style="background-color: #F8F9FA; padding: 30px 10px; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;">
        <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); border: 1px solid rgba(0,0,0,0.05);">
            <div style="background-color: {personality['color']}; padding: 45px 30px; text-align: center;">
                <h1 style="margin: 0; font-size: 4.5em; font-weight: 700; color: #ffffff; letter-spacing: -1.5px; line-height: 1;">{final_percent}</h1>
                <div style="font-size: 1.4em; font-weight: 600; color: rgba(255,255,255,0.95); margin-top: 12px; letter-spacing: 0.5px;">{attended} / {delivered}</div>
                <div style="font-size: 1.1em; color: rgba(255,255,255,0.85); font-weight: 600; margin-top: 10px; text-transform: uppercase; letter-spacing: 1.2px;">{personality['status']}</div>
            </div>
            <div style="background-color: #FFFFFF; padding: 20px 30px; text-align: center; border-bottom: 1px solid #F1F3F4;">
                <p style="margin: 0; color: #5F6368; font-style: italic; font-size: 1em; font-weight: 400; line-height: 1.5;">
                    {personality['subject_icon']} "{personality['quote']}"
                </p>
            </div>
            <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                <thead>
                    <tr>
                        <th style="padding: 12px 20px; text-align: left; font-size: 0.7em; text-transform: uppercase; color: #9AA0A6; font-weight: 700; letter-spacing: 0.8px;">Subject</th>
                        <th style="padding: 12px 20px; text-align: right; font-size: 0.7em; text-transform: uppercase; color: #9AA0A6; font-weight: 700; letter-spacing: 0.8px;">Overall</th>
                        <th style="padding: 12px 20px; text-align: right; font-size: 0.7em; text-transform: uppercase; color: #9AA0A6; font-weight: 700; letter-spacing: 0.8px;">Yesterday</th>
                    </tr>
                </thead>
                <tbody>
                    {table_html}
                </tbody>
            </table>
            <div style="padding: 20px; text-align: center; font-size: 0.75em; color: #BDC1C6; border-top: 1px solid #F1F3F4; background-color: #FFFFFF;">
                NIET Attendance Bot • <a href="https://attendance-notify.vercel.app/" style="color:#BDC1C6; text-decoration:underline;">Update Settings</a>
            </div>
        </div>
    </div>
    """
    return subject_line, html_body


# ----------------------------------------------------------------------------
# PURE PARSING (no browser needed - unit-testable)
# ----------------------------------------------------------------------------
def col_index(headers, *keys):
    """Index of the first header containing ALL the given words (case-insens)."""
    for i, h in enumerate(headers):
        hl = (h or "").lower()
        if all(k in hl for k in keys):
            return i
    return None


def to_int(s):
    m = re.search(r"-?\d+", (s or "").replace(",", ""))
    return int(m.group()) if m else None


def to_float(s):
    m = re.search(r"-?\d+(?:\.\d+)?", (s or "").replace(",", ""))
    return float(m.group()) if m else None


def parse_date(s):
    """'Oct 09,2026' / 'OCT 09, 2026' / '09-10-2026' / '2026-10-09' -> date."""
    s = (s or "").strip()
    m = re.search(r"([A-Za-z]{3})[A-Za-z]*\.?\s*(\d{1,2})\s*,?\s*(\d{4})", s)
    if m:
        try:
            return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%b %d %Y").date()
        except ValueError:
            pass
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(s.split()[0] if s else "", fmt).date()
        except (ValueError, IndexError):
            continue
    return None


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip().lower()


STATUS_RE = re.compile(r"^(p|a|l|od|present|absent|leave)$", re.I)


def parse_attendance(tables):
    """
    tables: output of EXTRACT_TABLES_JS (rows are {"tag", "cells"}). Returns the
    subjects from the first table that has Course Name + Present + (Total Count | Absent).
    """
    for t in tables:
        h = t["headers"]
        c_name = col_index(h, "course", "name")
        c_code = col_index(h, "course", "code")
        c_pres = col_index(h, "present")
        c_abs = col_index(h, "absent")
        c_tot = col_index(h, "total", "count")
        c_pct = col_index(h, "percent")
        if c_name is None or c_pres is None or (c_tot is None and c_abs is None):
            continue

        link_cols = [c for c in (c_tot, c_pres, c_abs, c_pct) if c is not None]
        subjects = []
        for row in t["rows"]:
            r = row["cells"]
            if len(r) != len(h):          # footer / spacer rows
                continue
            name = r[c_name]["text"]
            if not re.search(r"[A-Za-z]", name):
                continue
            present = to_int(r[c_pres]["text"])
            if present is None:
                continue
            if c_tot is not None:
                total = to_int(r[c_tot]["text"])
            else:
                absent = to_int(r[c_abs]["text"])
                total = None if absent is None else present + absent
            if total is None:
                continue
            pct = to_float(r[c_pct]["text"]) if c_pct is not None else None
            if pct is None:
                pct = round(present / total * 100, 2) if total else 0.0
            link = next((r[c] for c in link_cols if r[c]["tag"]), None)
            subjects.append({
                "name": name,
                "code": r[c_code]["text"] if c_code is not None else "",
                "present": present,
                "total": total,
                "percent": pct,
                "row_tag": row.get("tag"),   # the whole <tr onclick=...> (current portal)
                "link": link,                # a link inside a count cell (older portal)
                "yesterday": "-",
            })
        if subjects:
            return subjects
    return []


def detail_table(tables):
    """
    Find the per-subject attendance detail table: a table with a date column and a
    status column. Columns are found by header name, else by what the cells contain.
    """
    for t in tables:
        h = t["headers"]
        ncol = len(h)
        rows = [row["cells"] for row in t["rows"] if row["cells"]]
        if not rows or ncol == 0:
            continue

        def values(c):
            return [r[c]["text"] for r in rows if len(r) == ncol and r[c]["text"]]

        c_date = col_index(h, "date")
        c_stat = col_index(h, "status")
        if c_date is None:
            for c in range(ncol):
                v = values(c)
                if v and all(parse_date(x) for x in v):
                    c_date = c
                    break
        if c_stat is None:
            for c in range(ncol):
                v = values(c)
                if v and all(STATUS_RE.match(x.strip()) for x in v):
                    c_stat = c
                    break
        if c_date is None or c_stat is None or c_date == c_stat:
            continue
        return {"c_date": c_date, "c_stat": c_stat, "rows": rows}
    return None


def detail_fingerprint(tables):
    dt = detail_table(tables)
    if dt is None:
        return None
    return json.dumps([[c["text"] for c in r] for r in dt["rows"]])


def parse_detail(tables, day):
    """
    Status strings recorded on `day` ([] = detail table found, nothing that day),
    or None if no detail table is on the page.
    """
    dt = detail_table(tables)
    if dt is None:
        return None
    need = max(dt["c_date"], dt["c_stat"])
    out = []
    for r in dt["rows"]:
        if len(r) > need and parse_date(r[dt["c_date"]]["text"]) == day:
            out.append(r[dt["c_stat"]]["text"].strip().upper())
    return out


# ----------------------------------------------------------------------------
# BROWSER HELPERS
# ----------------------------------------------------------------------------
# Returns every table whose header row contains ALL the given words (none = every table,
# header = its first row). Each body row is {tag, cells}; `tag` marks the element to click
# for that row (the <tr> itself when it has an onclick, else a link/onclick inside it).
EXTRACT_TABLES_JS = r"""
const need = (arguments[0] || []).map(s => s.toLowerCase());
const norm = s => (s || '').replace(/\s+/g, ' ').trim();
const txt = e => norm(e.innerText || e.textContent);
const out = [];
document.querySelectorAll('table').forEach((t, ti) => {
  const rows = Array.from(t.rows);
  let h = -1;
  for (let i = 0; i < rows.length; i++) {
    const line = Array.from(rows[i].cells).map(txt).join(' | ').toLowerCase();
    if (need.every(k => line.includes(k))) { h = i; break; }
  }
  if (h < 0) return;
  const headers = Array.from(rows[h].cells).map(txt);
  const body = [];
  for (let i = h + 1; i < rows.length; i++) {
    let rtag = null;
    if (rows[i].hasAttribute('onclick')) {          // <tr onclick="getStudentAttendanceDetails(...)">
      rtag = 'row-' + ti + '-' + i;
      rows[i].setAttribute('data-bot-row', rtag);
    }
    const cells = Array.from(rows[i].cells).map((c, ci) => {
      const a = c.matches('[onclick]') ? c : c.querySelector('a, [onclick]');
      let tag = null;
      if (a) { tag = 'bot-' + ti + '-' + i + '-' + ci; a.setAttribute('data-bot-link', tag); }
      return { text: txt(c), abs: a ? (a.href || '') : '', tag: tag };
    });
    body.push({ tag: rtag, cells: cells });
  }
  out.push({ headers: headers, rows: body });
});
return out;
"""

# Heading of the inline detail panel: "Attendance Details of <subject name>"
PANEL_HEADING_JS = r"""
const norm = s => (s || '').replace(/\s+/g, ' ').trim();
let best = null;
document.querySelectorAll('body *').forEach(e => {
  const t = norm(e.textContent);
  if (t.length < 200 && /^Attendance Details of\s+\S/i.test(t) && (best === null || t.length < best.length)) best = t;
});
return best === null ? null : best.replace(/^Attendance Details of\s+/i, '');
"""

# The dashboard widget: a leaf element like "16.22%" whose nearby parent says "Attendance".
FIND_WIDGET_JS = r"""
const re = /^\d+(\.\d+)?\s*%$/;
const els = Array.from(document.querySelectorAll('body *'))
  .filter(e => e.children.length === 0 && re.test((e.textContent || '').trim()));
for (const e of els) {
  let p = e;
  for (let i = 0; i < 4 && p.parentElement; i++) {
    p = p.parentElement;
    const t = (p.textContent || '').trim();
    if (/attendance/i.test(t) && t.length < 120) return e;
  }
}
return null;
"""


def safe_click(driver, element):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
    time.sleep(0.5)
    driver.execute_script("arguments[0].click();", element)


def find_first(driver, selectors, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        for by, sel in selectors:
            try:
                for el in driver.find_elements(by, sel):
                    if el.is_displayed():
                        return el
            except WebDriverException:
                pass
        time.sleep(0.5)
    raise TimeoutException(f"none of {[s for _, s in selectors]} found")


def read_attendance_table(driver, timeout=30):
    """Poll until the overview table parses into subjects. [] on timeout."""
    end = time.time() + timeout
    while True:
        try:
            tables = driver.execute_script(EXTRACT_TABLES_JS, ["course name"])
            subjects = parse_attendance(tables)
            if subjects:
                return subjects
        except WebDriverException:
            pass
        if time.time() >= end:
            return []
        time.sleep(1)


def describe_page(driver):
    """Structure only (URL, title, table headers). No student data."""
    lines = []
    try:
        lines.append(f"url   : {driver.current_url}")
        lines.append(f"title : {driver.title!r}")
        info = driver.execute_script(r"""
            const norm = s => (s||'').replace(/\s+/g,' ').trim();
            return {
              iframes: document.querySelectorAll('iframe').length,
              tables: Array.from(document.querySelectorAll('table')).map((t, i) => ({
                i: i, id: t.id, cls: t.className, rows: t.rows.length,
                head: t.rows.length
                  ? Array.from(t.rows[0].cells).map(c => norm(c.innerText || c.textContent)).join(' | ').slice(0, 300)
                  : ''
              }))
            };""")
        lines.append(f"iframes: {info['iframes']}   tables: {len(info['tables'])}")
        for t in info["tables"]:
            lines.append(f"  table[{t['i']}] id={t['id']!r} class={t['cls']!r} rows={t['rows']} header={t['head']!r}")
    except Exception as e:
        lines.append(f"(describe_page failed: {e})")
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# PORTAL FLOW
# ----------------------------------------------------------------------------
def login(driver, user_id, password):
    driver.get(LOGIN_URL)
    try:
        user_el = find_first(driver, USERNAME_SELECTORS, 30)
        pass_el = find_first(driver, PASSWORD_SELECTORS, 10)
        btn_el = find_first(driver, SUBMIT_SELECTORS, 10)
    except TimeoutException as e:
        raise LayoutError(f"Login form not found: {e}")

    user_el.clear()
    user_el.send_keys(user_id)
    pass_el.clear()
    pass_el.send_keys(password)
    safe_click(driver, btn_el)

    end = time.time() + 30
    while time.time() < end:
        if "home.htm" in driver.current_url:
            return
        time.sleep(1)

    url = driver.current_url
    if "login" in url.lower():
        raise LoginError("Still on the login page after submitting (bad credentials?)")
    raise LayoutError(f"After login landed on unexpected URL: {url}")


def _strategy_by_id(driver):
    # <h3 id="attendencePer">15.79%</h3> inside the clickable dashboard card
    safe_click(driver, driver.find_element(By.ID, "attendencePer"))


def _strategy_percent_widget(driver):
    el = driver.execute_script(FIND_WIDGET_JS)
    if el is None:
        raise LayoutError("percentage widget not found")
    safe_click(driver, el)


def _strategy_old_xpath(driver):
    xp = (
        "//*[contains(translate(text(), 'ATTENDANCE', 'attendance'), 'attendance')]"
        "/ancestor::*[contains(., '%')][1]"
    )
    el = driver.find_elements(By.XPATH, xp)[0]
    safe_click(driver, el)


def _strategy_sidebar(driver):
    el = driver.find_elements(
        By.XPATH, "//a[contains(translate(., 'ATTENDANCE', 'attendance'), 'attendance')]"
    )[0]
    safe_click(driver, el)


def open_attendance(driver):
    time.sleep(2)
    for strategy in (_strategy_by_id, _strategy_percent_widget, _strategy_old_xpath, _strategy_sidebar):
        try:
            strategy(driver)
        except Exception as e:
            print(f"   ↪ {strategy.__name__} failed: {str(e).splitlines()[0] if str(e) else type(e).__name__}")
            continue
        try:
            WebDriverWait(driver, 10).until(EC.url_contains("studentCourses"))
            print(f"   ✅ On attendance page ({strategy.__name__})")
            return
        except TimeoutException:
            print(f"   ↪ {strategy.__name__}: click did not navigate")
    raise LayoutError("Could not reach the attendance page from the dashboard")


def ensure_overview(driver):
    """
    The detail panel loads inline, so normally the overview is still there. If a click
    ever navigated away, get back to it.
    """
    if read_attendance_table(driver, timeout=6):
        return
    try:
        driver.back()
        if read_attendance_table(driver, timeout=10):
            return
    except WebDriverException:
        pass
    driver.get(HOME_URL)
    open_attendance(driver)
    if not read_attendance_table(driver, timeout=30):
        raise LayoutError("Could not return to the attendance overview")


def scrape_yesterday(driver, subject_name, day):
    """
    Click the subject's row; the portal fills 'Attendance Details of <subject>' below the
    table. Returns 'Present' | 'Absent' | 'No Class' | 'Unknown'. Never raises.
    """
    try:
        tables = driver.execute_script(EXTRACT_TABLES_JS, ["course name"])
        me = next((s for s in parse_attendance(tables) if s["name"] == subject_name), None)
        if me is None:
            print("      (subject row not found)")
            return "Unknown"
        if me["row_tag"]:
            selector = f"[data-bot-row='{me['row_tag']}']"
        elif me["link"]:
            selector = f"[data-bot-link='{me['link']['tag']}']"
        else:
            print("      (row is not clickable)")
            return "Unknown"

        # What the panel shows BEFORE the click, so we never mistake the previous subject's data for this one.
        before = detail_fingerprint(driver.execute_script(EXTRACT_TABLES_JS, []))
        safe_click(driver, driver.find_element(By.CSS_SELECTOR, selector))

        want = norm(subject_name)
        start = time.time()
        statuses = None
        while time.time() - start < 20:
            time.sleep(1)
            heading = driver.execute_script(PANEL_HEADING_JS)
            page_tables = driver.execute_script(EXTRACT_TABLES_JS, [])
            found = parse_detail(page_tables, day)
            if found is None:
                continue
            changed = detail_fingerprint(page_tables) != before
            if heading is not None and norm(heading) == want:
                statuses = found
                break
            if changed and (heading is None or time.time() - start > 8):
                statuses = found          # heading missing/odd format: trust a changed table
                break

        if statuses is None:
            print("      (detail panel did not load for this subject)")
            return "Unknown"
        if not statuses:
            return "No Class"
        return "Present" if all(s.startswith("P") for s in statuses) else "Absent"
    except Exception as e:
        print(f"      (detail scrape failed: {str(e).splitlines()[0] if str(e) else type(e).__name__})")
        return "Unknown"


# ----------------------------------------------------------------------------
# PER-USER PROCESSING
# ----------------------------------------------------------------------------
def run_once(driver, user, password, recipient):
    user_id = user["college_id"]
    day = (datetime.now(IST) - timedelta(days=1)).date()

    print("   ⏳ Logging in...")
    login(driver, user_id, password)
    print("   ✅ Logged in")

    if (user.get("fail_count") or 0) > 0:
        try:
            supabase.table("users").update({"fail_count": 0}).eq("college_id", user_id).execute()
        except Exception as e:
            print(f"   ⚠️ Could not reset fail_count: {e}")

    print("   🧭 Opening attendance page...")
    open_attendance(driver)

    print("   📊 Reading attendance table...")
    subjects = read_attendance_table(driver, timeout=30)
    if not subjects:
        raise LayoutError("Attendance table not found or not parseable")
    print(f"   ✅ {len(subjects)} subjects parsed")

    print(f"   📅 Checking yesterday ({day.isoformat()})...")
    for s in subjects:
        if s["total"] == 0:
            continue
        print(f"   🔍 {s['name']}")
        s["yesterday"] = scrape_yesterday(driver, s["name"], day)
        print(f"      → {s['yesterday']}")

    attended = sum(s["present"] for s in subjects)
    delivered = sum(s["total"] for s in subjects)
    overall = round(attended / delivered * 100, 2) if delivered else None

    subject_line, page = build_email(overall, attended, delivered, subjects)
    if not send_email_via_api(recipient, subject_line, page):
        raise RuntimeError("Email could not be sent")


def process_user(user):
    user_id = user["college_id"]
    fails = user.get("fail_count") or 0
    print(f"🔄 Processing: {user_id} (strikes: {fails}/{MAX_STRIKES})")

    db_email = (user.get("target_email") or "").strip().lower()
    if db_email != BETA_RECIPIENT:
        print(f"   ℹ️ DB target_email is {db_email!r}; beta sends to {BETA_RECIPIENT} only")

    try:
        password = cipher.decrypt(user["encrypted_pass"].encode()).decode()
    except Exception as e:
        print(f"   ❌ Cannot decrypt stored password: {e}")
        return False

    for attempt in (1, 2):
        driver = make_driver()
        try:
            run_once(driver, user, password, BETA_RECIPIENT)
            return True

        except LoginError as e:
            # Real credential problem: no retry (avoid locking the account), count a strike.
            print(f"   ❌ LOGIN FAILED: {e}")
            new_fail = fails + 1
            try:
                if new_fail >= MAX_STRIKES:
                    supabase.table("users").update(
                        {"is_active": False, "fail_count": new_fail}
                    ).eq("college_id", user_id).execute()
                    send_email_via_api(
                        BETA_RECIPIENT,
                        "🛑 Attendance bot deactivated (login failed 3 times)",
                        "<p>Login failed 3 times in a row, so the bot was switched off for "
                        f"<b>{html.escape(user_id)}</b>. Check the password, then set "
                        "<code>is_active = true, fail_count = 0</code> in Supabase.</p>",
                    )
                else:
                    supabase.table("users").update(
                        {"fail_count": new_fail}
                    ).eq("college_id", user_id).execute()
            except Exception as db_err:
                print(f"   ⚠️ Could not update strikes: {db_err}")
            return False

        except Exception as e:
            print(f"   ❌ Attempt {attempt} failed: {type(e).__name__}: {e}")
            traceback.print_exc()
            if attempt == 1:
                print("   🔄 Retrying once...")
                time.sleep(3)
                continue
            # Final attempt: site/layout trouble. NO strike. Tell the owner what it looked like.
            diag = describe_page(driver)
            print("   🧪 Page structure at failure:\n" + diag)
            notify_owner(
                "portal layout problem",
                f"User: {user_id}\nError: {type(e).__name__}: {e}\n\n{diag}",
            )
            return False

        finally:
            try:
                driver.quit()
            except Exception:
                pass
    return False


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard_id", type=int, default=0)
    parser.add_argument("--total_shards", type=int, default=1)
    args = parser.parse_args()

    print(f"🚀 BOT {BOT_VERSION} STARTED (BETA LOCK) — Worker {args.shard_id + 1} of {args.total_shards}")
    init_clients()

    rows = supabase.table("users").select("*").eq("college_id", BETA_USER).execute().data or []
    if not rows:
        if args.shard_id == 0:
            print(f"❌ No row in 'users' with college_id = {BETA_USER!r} "
                  "(check spelling/case, or the SUPABASE_URL/KEY secrets and RLS).")
            sys.exit(1)
        return
    user = rows[0]
    if not user.get("is_active"):
        if args.shard_id == 0:
            print(f"❌ Beta user exists but is_active = False (fail_count = {user.get('fail_count')}). "
                  "Set is_active = true and fail_count = 0 in Supabase.")
            sys.exit(1)
        return

    users = [user]
    mine = [u for i, u in enumerate(users) if i % args.total_shards == args.shard_id]
    if not mine:
        print("ℹ️ No users assigned to this worker.")
        return
    print(f"📋 This worker: {[u['college_id'] for u in mine]}")

    ok = True
    for u in mine:
        ok = process_user(u) and ok
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
