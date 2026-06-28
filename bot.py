import os
import json
import logging
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

OBS_USERNAME = os.getenv("OBS_USERNAME")
OBS_PASSWORD = os.getenv("OBS_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

CAS_LOGIN_URL = "https://jasig.firat.edu.tr/cas/login?service=https://obs.firat.edu.tr/oibs/std"
OBS_GRADES_FRAME = "not_listesi_op.aspx"
STATE_FILE = "state.json"

LETTER_GRADES = {"AA", "BA", "BB", "CB", "CC", "DC", "DD", "FD", "FF", "DZ", "YT", "YZ", "BT", "MU", "G", "K"}


def fetch_grades_playwright() -> list[dict]:
    """Login to OBS via CAS using a real browser, return grade rows."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        try:
            log.info("Navigating to CAS login...")
            page.goto(CAS_LOGIN_URL, timeout=30000)

            # Fill login form
            page.fill('input[name="username"]', OBS_USERNAME)
            page.fill('input[name="password"]', OBS_PASSWORD)
            page.press('input[name="password"]', "Enter")

            # Wait for OBS to load (URL should change to obs.firat.edu.tr)
            try:
                page.wait_for_url("**/obs.firat.edu.tr/**", timeout=20000)
            except PWTimeout:
                log.error("Login failed or timed out. Current URL: %s", page.url)
                # Check for error message on login page
                err = page.query_selector(".errors, #msg, .alert-danger")
                if err:
                    log.error("Login error: %s", err.inner_text())
                browser.close()
                return []

            log.info("CAS login success. URL: %s", page.url)

            # Wait for redirect chain to complete
            page.wait_for_load_state("networkidle", timeout=20000)
            log.info("Page settled. URL: %s", page.url)

            # Navigate to grades page
            # Open Not Listesi via sidebar menu click
            log.info("Opening Not Listesi...")
            page.get_by_text("Ders ve Dönem İşlemleri").first.click()
            page.wait_for_timeout(800)
            page.get_by_text("Not Listesi").first.click()
            page.wait_for_load_state("networkidle", timeout=20000)
            page.wait_for_timeout(1500)

            # Find the grades iframe
            grades_frame = None
            for frame in page.frames:
                if OBS_GRADES_FRAME in frame.url:
                    grades_frame = frame
                    log.info("Found grades frame: %s", frame.url)
                    break

            if not grades_frame:
                log.warning("Grades frame not found. Frames: %s", [f.url for f in page.frames])
                browser.close()
                return []

            # Wait for grade table to render inside frame
            try:
                grades_frame.wait_for_selector("table tr td", timeout=15000)
            except PWTimeout:
                log.warning("Grade table did not appear in frame within 15s")

            grades = _parse_grade_table(grades_frame)
            log.info("Parsed %d grade rows", len(grades))

            browser.close()
            return grades

        except Exception as e:
            log.exception("Playwright error: %s", e)
            try:
                browser.close()
            except Exception:
                pass
            return []


def _parse_grade_table(page) -> list[dict]:
    """Extract all rows from the first table on the page."""
    tables = page.query_selector_all("table")
    if not tables:
        log.warning("No tables found on: %s", page.url)
        return []

    best_table = None
    best_row_count = 0
    for table in tables:
        rows = table.query_selector_all("tr")
        if len(rows) > best_row_count:
            best_row_count = len(rows)
            best_table = table

    if not best_table or best_row_count < 2:
        log.warning("No suitable table found (max rows: %d)", best_row_count)
        return []

    rows = best_table.query_selector_all("tr")
    headers = [th.inner_text().strip() for th in rows[0].query_selector_all("th, td")]

    grades = []
    for row in rows[1:]:
        cells = [td.inner_text().strip() for td in row.query_selector_all("td")]
        if not cells:
            continue
        if headers:
            entry = dict(zip(headers, cells))
        else:
            entry = {str(i): v for i, v in enumerate(cells)}
        if any(entry.values()):
            grades.append(entry)

    return _expand_embedded(grades)


def _expand_embedded(grades: list[dict]) -> list[dict]:
    """OBS renders all courses as tab-delimited text inside a single cell.
    Detect that pattern and expand each row into its own dict."""
    expanded = []
    for g in grades:
        embedded = False
        for v in g.values():
            v = str(v)
            if "\t" in v and "\n" in v:
                lines = [l for l in v.split("\n") if l.strip()]
                if len(lines) >= 2:
                    col_headers = lines[0].split("\t")
                    for line in lines[1:]:
                        cells = line.split("\t")
                        entry = dict(zip(col_headers, cells))
                        if any(c.strip() for c in cells):
                            expanded.append(entry)
                    embedded = True
                    break
        if not embedded:
            expanded.append(g)
    return expanded


def _find_col(g: dict, keys: list) -> str:
    """Exact key match first, then substring. Avoids 'not' hitting 'Sınav Notları'."""
    for k, v in g.items():
        if any(k.lower() == key for key in keys) and v and str(v).strip():
            return str(v).strip()
    for k, v in g.items():
        if any(key in k.lower() for key in keys) and v and str(v).strip():
            return str(v).strip()
    return ""


def has_letter_grade(grade: dict) -> bool:
    values = " ".join(str(v) for v in grade.values()).upper().split()
    return bool(LETTER_GRADES.intersection(values))


def grade_key(grade: dict) -> str:
    return json.dumps(grade, ensure_ascii=False, sort_keys=True)


def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def send_telegram(message: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=15)
    if resp.ok:
        log.info("Telegram message sent")
    else:
        log.error("Telegram send failed: %s", resp.text)


def check_telegram_commands(state: dict) -> bool:
    """Poll Telegram for /kontrol. Returns True if found. Updates offset in state."""
    offset = state.get("last_update_id", 0)
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
            params={"offset": offset + 1, "timeout": 5},
            timeout=10,
        )
        updates = resp.json().get("result", []) if resp.ok else []
    except Exception as e:
        log.warning("getUpdates failed: %s", e)
        return False

    manual = False
    for upd in updates:
        uid = upd.get("update_id", 0)
        state["last_update_id"] = max(state.get("last_update_id", 0), uid)
        text = ((upd.get("message") or {}).get("text") or "").strip()
        if text.startswith("/kontrol"):
            log.info("Received /kontrol (update_id=%d)", uid)
            manual = True

    return manual


def format_status(grades: list[dict]) -> str:
    """Current grade summary for /kontrol response."""
    lines = ["📋 <b>Mevcut Not Durumu</b>\n"]
    for g in grades:
        kod  = _find_col(g, ["ders kodu", "kod"])
        ad   = _find_col(g, ["ders adı", "ders ad", "ad"])
        not_ = _find_col(g, ["not"])
        dur  = _find_col(g, ["sonuç.durumu", "sonuç.durum", "sonuc.durum", "sonu"])

        if not kod and not ad:
            continue
        if not_ and not_.strip():
            lines.append(f"✅ <b>{kod}</b> {ad} — <b>{not_}</b>")
        else:
            lines.append(f"⏳ <b>{kod}</b> {ad} — {dur or 'Bekleniyor'}")
    return "\n".join(lines)


def format_message(new_grades: list[dict]) -> str:
    lines = ["📢 <b>Yeni Not Açıklandı!</b>"]
    for g in new_grades:
        kod   = _find_col(g, ["ders kodu", "kod"])
        ad    = _find_col(g, ["ders adı", "ders ad", "ad"])
        not_  = _find_col(g, ["not"])
        ort   = _find_col(g, ["ort"])
        durum = _find_col(g, ["durumu", "durum"])
        sınav = _find_col(g, ["sınav notları", "sınav", "sinav"])

        if not kod and not ad:
            continue
        lines.append("")
        lines.append(f"<b>{kod} — {ad}</b>")
        if sınav:
            lines.append(f"🔢 {sınav}")
        lines.append(f"Not: <b>{not_}</b>  |  Ort: {ort}  |  {durum}")
    return "\n".join(lines)


NO_CHANGE_NOTIFY_HOURS = 5  # "henüz açıklanmadı" mesajı kaç saatte bir gitsin


def run() -> None:
    if not all([OBS_USERNAME, OBS_PASSWORD, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
        log.error("Missing env vars. Check .env file.")
        return

    state = load_state()

    # Check for /kontrol command before OBS fetch
    manual_check = check_telegram_commands(state)

    current_grades = fetch_grades_playwright()

    if not current_grades:
        log.warning("No grades fetched. Check bot.log for details.")
        save_state(state)
        return

    known_keys = set(state.get("grade_keys", []))
    first_run = not known_keys
    now_iso = datetime.now(timezone.utc).isoformat()

    if first_run:
        log.info("First run — saving %d grades as baseline, no notification", len(current_grades))
        send_telegram("✅ Bot aktif! Mevcut notlar kaydedildi, yeni not açıklandığında bildirim alacaksın.")
    else:
        new_with_letters = [g for g in current_grades if grade_key(g) not in known_keys and has_letter_grade(g)]

        if new_with_letters:
            log.info("New graded results: %d", len(new_with_letters))
            send_telegram(format_message(new_with_letters))
            state["last_no_change_notify"] = now_iso
        else:
            log.info("No new graded results")
            last_notify = state.get("last_no_change_notify")
            should_notify = True
            if last_notify:
                elapsed_hours = (datetime.now(timezone.utc) - datetime.fromisoformat(last_notify)).total_seconds() / 3600
                should_notify = elapsed_hours >= NO_CHANGE_NOTIFY_HOURS

            if should_notify:
                send_telegram("⏳ Henüz yeni bir sınav sonucu açıklanmadı.")
                state["last_no_change_notify"] = now_iso

        # /kontrol → mevcut durum özeti gönder
        if manual_check:
            send_telegram(format_status(current_grades))

    state["grade_keys"] = [grade_key(g) for g in current_grades]
    state["grades"] = current_grades
    save_state(state)


if __name__ == "__main__":
    run()
