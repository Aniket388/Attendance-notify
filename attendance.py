
"""
NIET attendance bot - PRODUCTION (V11.1)

Sends each active student's attendance report to THEIR OWN target_email.

Compared with V10.0
- Attendance table is read by HEADER NAMES (Course Name / Present Count / Total Count /
  Percentage), so the portal's recent layout change no longer breaks it.
- Yesterday's status is read from the inline "Attendance Details" panel.
- Only a real LoginError (bad credentials) counts toward the 3 strikes. Portal downtime,
  layout changes and mail problems never deactivate a student.
- Portal maintenance is detected and the rest of the worker's run is skipped.
- If the whole portal layout breaks, ONE alert email goes to OWNER_EMAIL (not to students).
- "Yesterday" uses India time; students are split across workers by a stable hash of their
  college id, so a user is never skipped or processed twice when other rows change mid-run.
- New HTML email design + plain-text twin.

Exit code stays 0 (like V10.0) so one failing worker can't cancel the other workers in a
GitHub matrix. Set the env var STRICT_EXIT=1 to make portal/mail problems turn the run red.
"""
import os
import re
import sys
import time
import json
import html
import base64
import argparse
import zlib
import traceback
from datetime import datetime, timedelta, timezone
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
BOT_VERSION = "V11.1"
LOGIN_URL = "https://nietcloud.niet.co.in/login.htm"
HOME_URL = "https://nietcloud.niet.co.in/home.htm"
IST = timezone(timedelta(hours=5, minutes=30), "IST")   # India has no DST, so a fixed offset is exact

OWNER_EMAIL = "jainaniket388@gmail.com"   # receives "portal problem" alerts (never students)
STRICT_EXIT = os.environ.get("STRICT_EXIT", "").strip() == "1"

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


class NoDataError(Exception):
    """The attendance table is there but lists no subjects yet (e.g. brand-new student). Skip quietly."""


class MailError(Exception):
    """Gmail refused / failed to send the report."""


class SiteDownError(Exception):
    """The portal is down / under maintenance. Not our fault, not the user's: skip quietly."""


DOWN_RE = re.compile(
    r"(down for maintenance|under maintenance|maintenance mode|temporarily unavailable|"
    r"service unavailable|bad gateway|gateway time-?out|be right back)",
    re.I,
)


def site_down_title(driver):
    """Strong, cheap signal: the page <title> says the site is down."""
    try:
        return bool(DOWN_RE.search(driver.title or ""))
    except Exception:
        return False


def is_site_down(driver):
    """Title or the first lines of the page say the site is down (only used after something already failed)."""
    if site_down_title(driver):
        return True
    try:
        body = driver.execute_script(
            "return document.body ? (document.body.innerText || '').slice(0, 600) : ''"
        ) or ""
        return bool(DOWN_RE.search(body))
    except Exception:
        return False


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
def send_email_via_api(target_email, subject, html_content, text_content=None):
    if not target_email or "@" not in target_email:
        print(f"   ❌ Email skipped: invalid recipient {target_email!r}")
        return False
    try:
        token = json.loads(os.environ.get("GMAIL_TOKEN_JSON", "").strip())
        creds = Credentials.from_authorized_user_info(token)
        service = build("gmail", "v1", credentials=creds)
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = "me"
        msg["To"] = target_email
        if text_content:
            msg.attach(MIMEText(text_content, "plain", "utf-8"))
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
    send_email_via_api(OWNER_EMAIL, f"🛠️ Attendance bot: {subject}", body)


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


# ----------------------------------------------------------------------------
# EMAIL DESIGN
# ----------------------------------------------------------------------------
TARGET = 75                 # attendance requirement (%): drawn as the marker on every bar
SHOW_TARGET_NOTES = True    # "Can miss N more" / "Attend next N to reach 75%" under each subject

FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif"
INK, MUTED, FAINT, HAIR = "#0F172A", "#6B7280", "#9CA3AF", "#EEF0F3"

_EMAIL_CSS = """
body{margin:0;padding:0;}
table{border-collapse:collapse;}
img{border:0;}
@media only screen and (max-width:620px){
  .container{width:100%!important;}
  .pad{padding-left:20px!important;padding-right:20px!important;}
  .hero-num{font-size:56px!important;line-height:60px!important;}
  .tile-val{font-size:19px!important;}
}
"""


def _tone(pct):
    """Status band for a percentage: label, message, colours (ink = on white, glow = on dark)."""
    if pct is None:
        return dict(label="No data", msg="No classes have been recorded yet.",
                    ink="#475569", glow="#94A3B8", soft="#F1F5F9")
    if pct >= 90:
        return dict(label="Excellent", msg=f"Comfortably above the {TARGET}% requirement.",
                    ink="#15803D", glow="#34D399", soft="#ECFDF3")
    if pct >= TARGET:
        return dict(label="On track", msg=f"Above the {TARGET}% requirement. Keep the momentum.",
                    ink="#15803D", glow="#34D399", soft="#ECFDF3")
    if pct >= 60:
        return dict(label="At risk", msg=f"Below the {TARGET}% requirement. Avoid further absences.",
                    ink="#B45309", glow="#FBBF24", soft="#FFF7E6")
    return dict(label="Critical", msg=f"Well below the {TARGET}% requirement. Immediate attention needed.",
                ink="#B42318", glow="#F87171", soft="#FEF3F2")


def classes_to_target(present, total, target=TARGET):
    """
    ('need', n): attend the next n classes in a row to reach `target`%.
    ('spare', n): can miss n more classes and stay at/above `target`%.
    None when there are no classes or the target is 0/100.
    """
    if total <= 0 or not 0 < target < 100:
        return None
    if present * 100 >= target * total:
        return ("spare", (100 * present - target * total) // target)
    need = -(-(target * total - 100 * present) // (100 - target))   # ceil
    return ("need", need)


def _target_note(present, total):
    r = classes_to_target(present, total)
    if r is None:
        return ""
    kind, n = r
    if kind == "need":
        return f"Attend the next {n} class{'es' if n != 1 else ''} to reach {TARGET}%"
    if n == 0:
        return f"At the {TARGET}% limit. Don't miss the next class"
    return f"Can miss {n} more class{'es' if n != 1 else ''}"


def _bar(pct, fill, track, tick, height=6, radius=3):
    """Progress bar built from table cells (works in Gmail/Outlook/Apple Mail) with a marker at TARGET%."""
    p = max(0.0, min(100.0, float(pct)))
    t = float(TARGET)
    if p < t:
        segs = [(p, fill), (t - p, track), ("tick", tick), (100 - t, track)]
    else:
        segs = [(t, fill), ("tick", tick), (p - t, fill), (100 - p, track)]
    cells = ""
    for w, color in segs:
        if w == "tick":
            cells += (f'<td width="2" style="width:2px;height:{height}px;line-height:{height}px;'
                      f'font-size:0;background-color:{color};">&nbsp;</td>')
        elif w > 0.05:
            cells += (f'<td width="{w:.2f}%" style="width:{w:.2f}%;height:{height}px;line-height:{height}px;'
                      f'font-size:0;background-color:{color};">&nbsp;</td>')
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="width:100%;border-collapse:separate;border-radius:{radius}px;overflow:hidden;"><tr>{cells}</tr></table>')


def _pill(status):
    if status == "Present":
        return (f"<span style=\"display:inline-block;padding:5px 11px;border-radius:999px;background-color:#E7F6EC;"
                f"color:#166534;font-family:{FONT};font-size:10.5px;font-weight:700;letter-spacing:.8px;\">PRESENT</span>")
    if status == "Absent":
        return (f"<span style=\"display:inline-block;padding:5px 11px;border-radius:999px;background-color:#FDECEA;"
                f"color:#B42318;font-family:{FONT};font-size:10.5px;font-weight:700;letter-spacing:.8px;\">ABSENT</span>")
    if status == "No Class":
        return f"<span style=\"font-family:{FONT};font-size:12px;color:{FAINT};\">No class</span>"
    return f"<span style=\"font-family:{FONT};font-size:14px;color:#D1D5DB;\">&ndash;</span>"


def _plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def _subject_row(s):
    tone = _tone(s["percent"])
    code = (s.get("code") or "").strip()
    if norm(code) == norm(s["name"]):
        code = ""
    caption = " &middot; ".join(
        x for x in (html.escape(code),
                    html.escape(_target_note(s["present"], s["total"])) if SHOW_TARGET_NOTES else "") if x
    )
    caption_html = (f'<div style="font-size:12px;line-height:18px;color:{MUTED};margin-top:2px;">{caption}</div>'
                    if caption else "")
    bar = _bar(s["percent"], tone["glow"] if s["percent"] >= TARGET else tone["ink"], "#E9ECF1", INK)
    return f"""
    <tr><td class="pad" style="padding:20px 32px 0 32px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="width:100%;"><tr>
        <td valign="top" style="font-family:{FONT};">
          <div style="font-size:14.5px;line-height:20px;font-weight:600;color:{INK};">{html.escape(s['name'])}</div>
          {caption_html}
        </td>
        <td valign="top" align="center" width="92" style="text-align:center;padding:0 8px;">{_pill(s.get('yesterday', '-'))}</td>
        <td valign="top" align="right" width="86" style="text-align:right;font-family:{FONT};">
          <div style="font-size:17px;line-height:22px;font-weight:700;color:{tone['ink']};letter-spacing:-.2px;">{s['percent']:.2f}%</div>
          <div style="font-size:12px;line-height:18px;color:{MUTED};">{s['present']} / {s['total']}</div>
        </td>
      </tr>
      <tr><td colspan="3" style="padding-top:12px;">{bar}</td></tr></table>
    </td></tr>
    <tr><td class="pad" style="padding:20px 32px 0 32px;"><div style="height:1px;line-height:1px;font-size:0;background-color:{HAIR};">&nbsp;</div></td></tr>"""


def _yesterday_summary(subjects):
    """(headline, colour) for the 'Yesterday' tile."""
    pres = sum(1 for s in subjects if s.get("yesterday") == "Present")
    absn = sum(1 for s in subjects if s.get("yesterday") == "Absent")
    unk = sum(1 for s in subjects if s.get("total", 0) > 0 and s.get("yesterday") not in ("Present", "Absent", "No Class"))
    if absn:
        return f"{absn} absent", "#B42318"
    if pres:
        return "All present", "#15803D"
    if unk:
        return "Unavailable", MUTED
    return "No classes", MUTED


def build_email(overall, attended, delivered, subjects, day=None):
    """High-end HTML email. Returns (subject_line, html_document)."""
    now = datetime.now(IST)
    tone = _tone(overall)
    overall_txt = "N/A" if overall is None else f"{overall:.2f}"
    day_label = day.strftime("%a, %d %b") if day else "Yesterday"
    missed = max(0, delivered - attended)
    y_head, y_color = _yesterday_summary(subjects)

    active = [s for s in subjects if s["total"] > 0]
    idle = [s for s in subjects if s["total"] == 0]
    rows = "".join(_subject_row(s) for s in active)
    if idle:
        rows += f"""
    <tr><td class="pad" style="padding:26px 32px 0 32px;font-family:{FONT};font-size:10.5px;font-weight:700;letter-spacing:1.4px;color:{FAINT};">NOT STARTED YET</td></tr>"""
        for s in idle:
            rows += f"""
    <tr><td class="pad" style="padding:10px 32px 0 32px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="width:100%;"><tr>
        <td style="font-family:{FONT};font-size:13px;line-height:19px;color:{MUTED};">{html.escape(s['name'])}</td>
        <td align="right" style="text-align:right;font-family:{FONT};font-size:12px;color:{FAINT};white-space:nowrap;padding-left:12px;">No classes held</td>
      </tr></table>
    </td></tr>"""

    hero_bar = (_bar(overall, tone["glow"], "#26354F", "#FFFFFF", height=8, radius=4) if overall is not None else "")
    hero_bar_block = f"""
        <div style="margin-top:26px;">{hero_bar}</div>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="width:100%;margin-top:8px;"><tr>
          <td style="font-family:{FONT};font-size:11.5px;color:#94A3B8;">Your attendance</td>
          <td align="right" style="text-align:right;font-family:{FONT};font-size:11.5px;color:#94A3B8;">Target {TARGET}%</td>
        </tr></table>""" if overall is not None else ""

    def tile(label, value, color, caption, first=False):
        border = "" if first else f"border-left:1px solid {HAIR};"
        return f"""
        <td width="33%" align="center" valign="top" style="text-align:center;width:33.33%;padding:20px 8px;{border}font-family:{FONT};">
          <div style="font-size:10.5px;font-weight:700;letter-spacing:1.3px;color:{FAINT};">{label}</div>
          <div class="tile-val" style="white-space:nowrap;font-size:22px;line-height:30px;font-weight:700;color:{color};margin-top:6px;letter-spacing:-.3px;">{value}</div>
          <div style="font-size:11.5px;line-height:16px;color:{MUTED};margin-top:2px;">{caption}</div>
        </td>"""

    tiles = (tile("ATTENDED", attended, INK, "classes", first=True)
             + tile("MISSED", missed, INK, "classes")
             + tile("YESTERDAY", y_head, y_color, html.escape(day_label)))

    preheader = (f"{overall_txt}{'' if overall is None else '%'} overall &middot; {attended} of {delivered} classes "
                 f"&middot; Yesterday: {y_head.lower()}")
    subject_line = f"{get_personality(overall)['subject_icon']} {get_personality(overall)['status']}: " \
                   f"{'N/A' if overall is None else str(overall) + '%'}"

    doc = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light">
<title>Attendance report</title><style>{_EMAIL_CSS}</style></head>
<body style="margin:0;padding:0;background-color:#F3F4F6;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{preheader}&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="#F3F4F6" style="width:100%;background-color:#F3F4F6;"><tr><td style="padding:32px 12px;text-align:left;">
  <table role="presentation" class="container" width="600" align="center" cellpadding="0" cellspacing="0" style="width:600px;max-width:600px;margin:0 auto;">

    <tr><td style="padding:0 6px 16px 6px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="width:100%;"><tr>
        <td>
          <table role="presentation" cellpadding="0" cellspacing="0"><tr>
            <td width="28" height="28" align="center" bgcolor="{INK}" style="width:28px;height:28px;background-color:{INK};border-radius:8px;color:#FFFFFF;font-family:{FONT};font-size:13px;line-height:28px;font-weight:700;text-align:center;">N</td>
            <td style="padding-left:10px;font-family:{FONT};font-size:13px;font-weight:600;color:#111827;letter-spacing:.2px;">NIET Attendance</td>
          </tr></table>
        </td>
        <td align="right" style="text-align:right;font-family:{FONT};font-size:12px;color:{MUTED};">{now.strftime('%a, %d %b %Y')}</td>
      </tr></table>
    </td></tr>

    <tr><td>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="#FFFFFF" style="width:100%;background-color:#FFFFFF;border:1px solid #E5E7EB;border-radius:16px;border-collapse:separate;overflow:hidden;">

        <tr><td class="pad" bgcolor="#0B1220" style="background-color:#0B1220;background-image:linear-gradient(160deg,#0B1220 0%,#16223D 100%);padding:34px 32px 30px 32px;border-radius:15px 15px 0 0;">
          <div style="font-family:{FONT};font-size:11px;font-weight:700;letter-spacing:1.8px;color:#94A3B8;">OVERALL ATTENDANCE</div>
          <div class="hero-num" style="font-family:{FONT};font-size:68px;line-height:72px;font-weight:700;color:#FFFFFF;letter-spacing:-2.5px;margin-top:10px;">{overall_txt}<span style="font-size:30px;line-height:30px;letter-spacing:0;font-weight:600;color:#94A3B8;">{'' if overall is None else '%'}</span></div>
          <div style="margin-top:14px;">
            <span style="display:inline-block;padding:5px 12px;border-radius:999px;background-color:#1A2742;border:1px solid #2B3C61;font-family:{FONT};font-size:12px;font-weight:600;color:{tone['glow']};letter-spacing:.3px;">&#9679;&nbsp; {tone['label']}</span>
            <span style="font-family:{FONT};font-size:13.5px;color:#CBD5E1;padding-left:10px;">{attended} of {delivered} classes attended</span>
          </div>{hero_bar_block}
          <div style="font-family:{FONT};font-size:13px;line-height:20px;color:#94A3B8;margin-top:18px;">{html.escape(tone['msg'])}</div>
        </td></tr>

        <tr><td style="border-bottom:1px solid {HAIR};">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="width:100%;"><tr>{tiles}</tr></table>
        </td></tr>

        <tr><td class="pad" style="padding:28px 32px 0 32px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="width:100%;"><tr>
            <td style="font-family:{FONT};font-size:11px;font-weight:700;letter-spacing:1.8px;color:{INK};">SUBJECT BREAKDOWN</td>
            <td width="92" align="center" style="text-align:center;width:92px;padding:0 8px;font-family:{FONT};font-size:10.5px;font-weight:700;letter-spacing:1.2px;color:{FAINT};">YESTERDAY</td>
            <td width="86" align="right" style="text-align:right;width:86px;font-family:{FONT};font-size:10.5px;font-weight:700;letter-spacing:1.2px;color:{FAINT};">OVERALL</td>
          </tr></table>
        </td></tr>
        {rows}
        <tr><td style="height:28px;line-height:28px;font-size:0;">&nbsp;</td></tr>
      </table>
    </td></tr>

    <tr><td align="center" style="text-align:center;padding:22px 12px 0 12px;font-family:{FONT};font-size:11.5px;line-height:18px;color:{FAINT};">
      Based on the records published on the college portal &middot; {now.strftime('%d %b %Y, %I:%M %p')} IST<br>
      NIET Attendance Bot &middot; {BOT_VERSION} &middot; <a href="https://attendance-notify.vercel.app/" style="color:{MUTED};text-decoration:underline;">Update settings</a>
    </td></tr>

  </table>
</td></tr></table>
</body></html>"""
    return subject_line, doc


def build_plain(overall, attended, delivered, subjects, day=None):
    """Plain-text twin of the email (better deliverability and notification previews)."""
    head = "N/A" if overall is None else f"{overall:.2f}%"
    lines = [f"OVERALL ATTENDANCE: {head}  ({attended} of {delivered} classes)", ""]
    for s in subjects:
        if s["total"] == 0:
            lines.append(f"- {s['name']}: no classes held yet")
        else:
            y = s.get("yesterday", "-")
            lines.append(f"- {s['name']}: {s['percent']:.2f}% ({s['present']}/{s['total']})"
                         + (f" | {day.strftime('%d %b') if day else 'Yesterday'}: {y}" if y not in ("-", "Unknown") else ""))
    lines += ["", f"NIET Attendance Bot - {BOT_VERSION}"]
    return "\n".join(lines)


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


def attendance_table_is_empty(driver):
    """
    True only when the attendance table (found by its headers) is on the page but has NO
    full-width subject rows (a brand-new student). If rows exist but could not be parsed,
    that is a layout change and must stay loud, so it returns False.
    """
    try:
        tables = driver.execute_script(EXTRACT_TABLES_JS, ["course name"])
    except WebDriverException:
        return False
    for t in tables:
        h = t["headers"]
        if col_index(h, "course", "name") is None:
            continue
        if col_index(h, "present") is None and col_index(h, "percent") is None:
            continue
        if all(len(row["cells"]) < len(h) - 2 for row in t["rows"]):
            return True
    return False


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
    if site_down_title(driver):
        raise SiteDownError(f"Portal says: {driver.title!r}")
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
        if attendance_table_is_empty(driver):
            raise NoDataError("attendance table is present but lists no subjects yet")
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

    subject_line, page = build_email(overall, attended, delivered, subjects, day)
    text = build_plain(overall, attended, delivered, subjects, day)
    if not send_email_via_api(recipient, subject_line, page, text):
        raise MailError("Email could not be sent (Gmail API error)")


def mask_id(college_id):
    """0231csiot122@niet.co.in -> 0231***22@niet.co.in (Actions logs of a public repo are world-readable)."""
    local, _, domain = (college_id or "").partition("@")
    masked = (local[:4] + "***" + local[-2:]) if len(local) > 6 else (local[:1] + "***")
    return f"{masked}@{domain}" if domain else masked


def process_user(user):
    """
    Process one student. Returns (outcome, detail); outcome is one of
    ok | login | down | layout | nodata | mail | skipped.
    """
    user_id = user["college_id"]
    fails = user.get("fail_count") or 0
    recipient = (user.get("target_email") or "").strip()
    print(f"\n🔄 Processing: {mask_id(user_id)} (strikes: {fails}/{MAX_STRIKES})")

    if "@" not in recipient:
        print("   ⚠️ No valid target_email stored; skipping this student.")
        return "skipped", "no valid target_email"

    try:
        password = cipher.decrypt(user["encrypted_pass"].encode()).decode()
    except Exception:
        print("   ❌ Decryption Failed")
        return "skipped", "decryption failed"

    for attempt in (1, 2):
        driver = None
        try:
            driver = make_driver()
            run_once(driver, user, password, recipient)
            return "ok", ""

        except LoginError as e:
            # Real credential problem: no retry (avoids locking the account), count a strike.
            print(f"   ❌ LOGIN FAILED: {e}")
            new_fail = fails + 1
            try:
                if new_fail >= MAX_STRIKES:
                    print("   💀 3 Strikes. Deactivating.")
                    supabase.table("users").update(
                        {"fail_count": new_fail, "is_active": False}
                    ).eq("college_id", user_id).execute()
                    send_email_via_api(
                        recipient,
                        "Bot Deactivated",
                        "<h1>Login Failed 3 Times</h1><p>Please update your password on the portal: "
                        "<a href='https://attendance-notify.vercel.app/'>Update Settings</a>.</p>",
                    )
                else:
                    supabase.table("users").update(
                        {"fail_count": new_fail}
                    ).eq("college_id", user_id).execute()
            except Exception as db_err:
                print(f"   ⚠️ Could not update strikes: {db_err}")
            return "login", str(e)

        except SiteDownError as e:
            print(f"   ⏸️ Portal is down (no strike, no retry): {e}")
            return "down", str(e)

        except NoDataError as e:
            print(f"   ℹ️ {e}; nothing to send.")
            return "nodata", str(e)

        except MailError as e:
            print(f"   ❌ {e}")
            return "mail", str(e)

        except Exception as e:
            if driver is not None and is_site_down(driver):
                print(f"   ⏸️ Portal went down mid-run ({type(e).__name__}) (no strike, no retry).")
                return "down", str(e)
            print(f"   ❌ Attempt {attempt} failed: {type(e).__name__}: {e}")
            traceback.print_exc()
            if attempt == 1:
                print("   🔄 Retrying once...")
                time.sleep(3)
                continue
            diag = describe_page(driver) if driver is not None else "(browser did not start)"
            print("   🧪 Page structure at failure:\n" + diag)
            return "layout", f"User: {user_id}\nError: {type(e).__name__}: {e}\n\n{diag}"

        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass
    return "layout", f"User: {user_id}\nExhausted attempts"


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------
def shard_of(college_id, total_shards):
    """Stable worker for a student: depends only on the id, never on which other rows exist."""
    return zlib.crc32((college_id or "").strip().lower().encode()) % total_shards


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard_id", type=int, default=0, help="Current Worker ID (0, 1, 2...)")
    parser.add_argument("--total_shards", type=int, default=1, help="Total number of Workers")
    args = parser.parse_args()
    total = max(1, args.total_shards)

    print(f"🚀 PRODUCTION BOT {BOT_VERSION} STARTED: Worker {args.shard_id + 1} of {total}")
    init_clients()

    try:
        all_users = supabase.table("users").select("*").eq("is_active", True).execute().data or []
    except Exception as e:
        print(f"🔥 CRITICAL ERROR: could not read the users table: {e}")
        print("::error title=Supabase unreachable::Could not read the users table.")
        sys.exit(1)

    if not all_users:
        print("   ⚠️ No users found in database.")
        return

    my_users = [u for u in all_users if shard_of(u.get("college_id"), total) == args.shard_id]
    print(f"📋 Total Active Users: {len(all_users)} | Worker Processing: {len(my_users)}")

    stats = {"ok": 0, "login": 0, "down": 0, "layout": 0, "nodata": 0, "mail": 0, "skipped": 0}
    layout_notes = []
    for idx, user in enumerate(my_users):
        try:
            outcome, detail = process_user(user)
        except Exception as e:                      # one odd student must never stop the worker
            traceback.print_exc()
            outcome, detail = "layout", f"User: {user.get('college_id')}\nUnexpected crash: {type(e).__name__}: {e}"
        stats[outcome] = stats.get(outcome, 0) + 1
        if outcome == "layout":
            layout_notes.append(detail)
        if outcome == "down":
            left = len(my_users) - idx - 1
            print(f"\n⏸️ Portal is down/under maintenance: skipping the remaining {left} student(s) in this worker.")
            print("::warning title=Portal down::NIET portal is down/under maintenance; some reports were not sent this run.")
            break

    print("\n📊 Worker summary: " + " | ".join(f"{k}={v}" for k, v in stats.items() if v))

    # A single odd student is just logged. If most of this worker's students failed the same way,
    # the portal itself changed: tell the owner once (students are never penalised for it).
    systemic = stats["layout"] >= 1 and stats["layout"] >= stats["ok"]
    if systemic:
        print("::error title=Portal layout problem::Most students failed to scrape; the portal layout probably changed.")
        notify_owner(
            "portal problem (production)",
            f"Worker {args.shard_id + 1}/{total}: {stats['layout']} of {len(my_users)} students failed with a "
            f"portal/layout problem, {stats['ok']} succeeded. No strikes were recorded.\n\nFirst failure:\n{layout_notes[0]}",
        )
    elif stats["layout"]:
        print(f"::warning title=Some students failed::{stats['layout']} student(s) failed with a portal/layout problem.")
    if stats["mail"]:
        print(f"::error title=Email sending failed::{stats['mail']} report(s) could not be emailed (check GMAIL_TOKEN_JSON).")

    if STRICT_EXIT and (systemic or stats["mail"]):
        sys.exit(1)


if __name__ == "__main__":
    main()
