"""
Frontier Model Watch — checks for new AI model releases and pings you on Telegram.

Runs on GitHub Actions (free). No AI or paid APIs involved.
Sources:
  1. AI Release Tracker (aireleasetracker.com) — tracks OpenAI, Anthropic, Google,
     Meta, xAI, DeepSeek, Mistral, Moonshot, Z.ai, Qwen, NVIDIA.
  2. Official news feeds from OpenAI and Google (backup, filtered to model launches).

State lives in seen.json, which the workflow commits back to the repo.
"""
import html
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

STATE_FILE = "seen.json"
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "").strip()
TEST_MODE = os.environ.get("TEST_MODE", "false").lower() == "true"

TRACKER_URL = "https://aireleasetracker.com/latest"
FEEDS = {
    "OpenAI": "https://openai.com/news/rss.xml",
    "Google": "https://blog.google/technology/ai/rss/",
    "Google DeepMind": "https://deepmind.google/blog/rss.xml",
}
# Only feed posts whose title looks like a model launch.
MODEL_WORDS = re.compile(r"\b(GPT|o\d|Gemini|Gemma|Claude|Sora|Veo|Imagen|model)\b", re.I)
LAUNCH_WORDS = re.compile(r"\b(introduc|launch|releas|announc|meet|now available)", re.I)

UA = {"User-Agent": "frontier-model-watch/1.0 (+github actions)"}


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def tracker_releases():
    """Return {key: {name, lab, url}} from the tracker's latest page."""
    page = fetch(TRACKER_URL)
    found = {}
    # Links look like /model/<lab>/<slug>, often with title="<Model> by <Lab>".
    for m in re.finditer(r'href="((?:https://aireleasetracker\.com)?/model/([a-z0-9-]+)/([^"/#?]+))"([^>]*)>', page):
        href, lab_slug, slug, rest = m.groups()
        key = f"tracker:{lab_slug}/{slug}"
        if key in found:
            continue
        name, lab = None, lab_slug.replace("-", " ").title()
        t = re.search(r'title="([^"]+)"', rest)
        if t:
            title = html.unescape(t.group(1))
            if " by " in title:
                name, lab = title.rsplit(" by ", 1)
            else:
                name = title.split(" · ")[0]
        if not name:
            name = slug.replace("-", " ").title()
        url = href if href.startswith("http") else "https://aireleasetracker.com" + href
        found[key] = {"name": name.strip(), "lab": lab.strip(), "url": url}
    return found


def feed_releases():
    found = {}
    for lab, url in FEEDS.items():
        try:
            root = ET.fromstring(fetch(url))
        except Exception as e:  # a broken feed should never stop the run
            print(f"feed {lab} skipped: {e}")
            continue
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            if not title or not link:
                continue
            if MODEL_WORDS.search(title) and LAUNCH_WORDS.search(title):
                found[f"feed:{link}"] = {"name": title, "lab": lab, "url": link}
    return found


def send(text):
    if not TOKEN or not CHAT_ID:
        print("Telegram secrets missing; message would be:\n" + text)
        return
    data = json.dumps({"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML",
                       "disable_web_page_preview": False}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                                 data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()


def fmt(item, source_label):
    e = html.escape
    lines = [f"<b>New AI model: {e(item['name'])}</b>",
             f"{e(item['lab'])} · spotted {datetime.now(timezone.utc):%b %d, %H:%M} UTC",
             f'<a href="{e(item["url"])}">Release details</a> ({source_label})']
    if DASHBOARD_URL:
        lines.append(f'<a href="{e(DASHBOARD_URL)}">Open the Frontier Model Ledger</a>')
    return "\n".join(lines)


def main():
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
    except FileNotFoundError:
        state = {}
    seen = set(state.get("seen", []))
    first_run = not seen

    if TEST_MODE:
        send("<b>Frontier Model Watch is connected.</b>\nYou'll get a message here whenever a new AI model is released."
             + (f'\n<a href="{html.escape(DASHBOARD_URL)}">Open the Frontier Model Ledger</a>' if DASHBOARD_URL else ""))

    current = {}
    errors = []
    try:
        current.update({k: (v, "AI Release Tracker") for k, v in tracker_releases().items()})
    except Exception as e:
        errors.append(f"tracker: {e}")
    fr = feed_releases()
    current.update({k: (v, "official blog") for k, v in fr.items()})
    print(f"found {len(current)} items, {len(seen)} already seen")

    new = [k for k in current if k not in seen]
    if first_run:
        print("first run: recording existing releases without notifying")
        send(f"<b>Frontier Model Watch is live.</b>\nTracking {len(current)} existing releases. "
             "You'll be pinged here for anything new.")
    else:
        # Avoid a flood if a source changes its page layout.
        if len(new) > 8:
            send(f"<b>Frontier Model Watch:</b> {len(new)} new items appeared at once, "
                 "likely a source layout change. Showing the first 3.")
            new = new[:3]
        for k in new:
            item, label = current[k]
            send(fmt(item, label))
            print("notified:", item["name"])

    seen.update(current.keys())
    state["seen"] = sorted(seen)
    now = datetime.now(timezone.utc)
    # Monthly heartbeat commit keeps GitHub from pausing the schedule after 60 quiet days.
    hb = state.get("heartbeat")
    if not hb or (now - datetime.fromisoformat(hb)).days >= 25:
        state["heartbeat"] = now.isoformat(timespec="seconds")
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=1)

    if errors and not fr:
        print("all sources failed:", errors)
        sys.exit(1)  # GitHub emails you when a run fails


if __name__ == "__main__":
    main()
