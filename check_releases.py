"""
Frontier Model Watch v2 — pings you on Telegram when a new AI model is released.

Runs on GitHub Actions (free). No AI or paid APIs involved.
Sources (both give clean model names):
  1. AI Release Tracker (aireleasetracker.com/latest) — curated list of major-lab releases.
  2. OpenRouter's public model catalog — new models from major labs as soon as they're served.

The same model seen in both sources only triggers one message.
A source seen for the first time is recorded silently, so it can't flood you.
State lives in seen.json, which the workflow commits back to the repo.
"""
import html
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

STATE_FILE = "seen.json"
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "").strip()
TEST_MODE = os.environ.get("TEST_MODE", "false").lower() == "true"

TRACKER_URL = "https://aireleasetracker.com/latest"
OPENROUTER_URL = "https://openrouter.ai/api/v1/models"

# OpenRouter provider prefix -> lab name. Only these labs are reported.
LABS = {
    "openai": "OpenAI", "anthropic": "Anthropic", "google": "Google", "x-ai": "xAI",
    "meta-llama": "Meta", "meta": "Meta", "deepseek": "DeepSeek", "qwen": "Alibaba Qwen",
    "mistralai": "Mistral", "moonshotai": "Moonshot", "z-ai": "Z.ai", "nvidia": "NVIDIA",
}
MAX_SINGLE = 6  # more new models than this in one run -> one digest message

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/129.0 Safari/537.36",
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def norm(name):
    """'GPT-6.1 Sol' and 'gpt 6.1 sol' -> 'gpt61sol' so sources dedupe."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def tracker_models():
    page = fetch(TRACKER_URL)
    out = {}
    # Preferred: the page's structured data, e.g. {"url": ".../model/google/x", "name": "X by Google"}
    for url, title in re.findall(r'"url":"(https://aireleasetracker\.com/model/[^"]+)","name":"([^"]+)"', page):
        name, _, lab = html.unescape(title).rpartition(" by ")
        if name:
            out["model:" + norm(name)] = {"name": name.strip(), "lab": lab.strip(), "url": url, "date": None}
    # Fallback: plain links like href="/model/google/gemini-4-argon"
    if not out:
        for lab_slug, slug in re.findall(r'href="(?:https://aireleasetracker\.com)?/model/([a-z0-9-]+)/([^"/#?]+)"', page):
            name = slug.replace("-", " ").title()
            out.setdefault("model:" + norm(name), {
                "name": name, "lab": lab_slug.replace("-", " ").title(),
                "url": f"https://aireleasetracker.com/model/{lab_slug}/{slug}", "date": None})
    return out


def openrouter_models():
    data = json.loads(fetch(OPENROUTER_URL)).get("data", [])
    out = {}
    for m in data:
        mid = m.get("id", "")
        if ":" in mid or "/" not in mid:  # skip :free / :batch / :thinking variants
            continue
        prefix = mid.split("/", 1)[0]
        if prefix not in LABS:
            continue
        name = m.get("name", mid).split(": ", 1)[-1]
        name = re.sub(r"\s*\((free|batch|preview)\)$", "", name, flags=re.I).strip()
        created = m.get("created")
        date = datetime.fromtimestamp(created, timezone.utc).strftime("%b %d, %Y") if created else None
        out["model:" + norm(name)] = {"name": name, "lab": LABS[prefix],
                                      "url": f"https://openrouter.ai/{mid}", "date": date}
    return out


def send(text):
    if not TOKEN or not CHAT_ID:
        print("Telegram secrets missing; message would be:\n" + text)
        return
    data = json.dumps({"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML",
                       "disable_web_page_preview": True}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                                 data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()


def dash_line():
    return f'\n<a href="{html.escape(DASHBOARD_URL)}">Open the Frontier Model Ledger</a>' if DASHBOARD_URL else ""


def fmt_one(m):
    e = html.escape
    when = m["date"] or f"spotted {datetime.now(timezone.utc):%b %d, %Y}"
    return (f"<b>New AI model: {e(m['name'])}</b>\n"
            f"{e(m['lab'])} · {e(when)}\n"
            f'<a href="{e(m["url"])}">Release details</a>' + dash_line())


def fmt_digest(ms):
    e = html.escape
    lines = [f"<b>{len(ms)} new AI models</b>"]
    lines += [f'• <a href="{e(m["url"])}">{e(m["name"])}</a> · {e(m["lab"])}' for m in ms[:12]]
    if len(ms) > 12:
        lines.append(f"…and {len(ms) - 12} more")
    return "\n".join(lines) + dash_line()


def main():
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
    except FileNotFoundError:
        state = {}
    seen = set(state.get("seen", []))
    seeded = set(state.get("seeded_sources", []))

    if TEST_MODE:
        send("<b>Frontier Model Watch is connected.</b>\n"
             "You'll get a message here whenever a new AI model is released." + dash_line())

    sources = {"tracker": tracker_models, "openrouter": openrouter_models}
    new, ok = {}, 0
    for sname, fn in sources.items():
        try:
            items = fn()
        except Exception as e:
            print(f"{sname}: FAILED ({e})")
            continue
        print(f"{sname}: {len(items)} models")
        if not items:
            continue
        ok += 1
        if sname not in seeded:
            print(f"{sname}: first successful read, recording silently")
            seen.update(items)
            seeded.add(sname)
            continue
        for k, m in items.items():
            if k not in seen and k not in new:
                new[k] = m

    fresh = list(new.values())
    if fresh:
        if len(fresh) > MAX_SINGLE:
            send(fmt_digest(fresh))
        else:
            for m in fresh:
                send(fmt_one(m))
        for m in fresh:
            print("notified:", m["name"], "|", m["lab"])
    seen.update(new)

    state["seen"] = sorted(seen)
    state["seeded_sources"] = sorted(seeded)
    now = datetime.now(timezone.utc)
    hb = state.get("heartbeat")  # monthly commit keeps GitHub from pausing the schedule
    if not hb or (now - datetime.fromisoformat(hb)).days >= 25:
        state["heartbeat"] = now.isoformat(timespec="seconds")
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=1)

    if ok == 0:
        print("all sources failed")
        sys.exit(1)  # GitHub emails you when a run fails


if __name__ == "__main__":
    main()
