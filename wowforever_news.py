#!/usr/bin/env python3
"""Posts new WoW Forever news and patch notes to a Discord channel.

Reads an RSS feed (Wowhead's Forever feed by default), remembers what it
already posted and sends each new item to a Discord webhook as an embed.
Standard library only.

Usage:
  export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
  python3 wowforever_news.py              # one check, good for cron
  python3 wowforever_news.py --loop 900   # check every 15 minutes forever
  python3 wowforever_news.py --dry-run    # print instead of posting
"""
import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

DEFAULT_FEED = "https://www.wowhead.com/forever/news/rss/forever"
DEFAULT_STATE = Path(__file__).with_name("seen.json")
MEDIA_NS = "{http://search.yahoo.com/mrss/}"
USER_AGENT = "wow-forever-discord-announcer/1.0"

PATCH_WORDS = re.compile(
    r"patch notes|development notes|beta build|beta update|new build|hotfix|maintenance|changelog",
    re.I,
)
COLOR_PATCH = 0xE67E22
COLOR_NEWS = 0x3498DB


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def plain(text):
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("Continue reading »", "")
    return re.sub(r"\s+", " ", text).strip()


def parse_feed(raw):
    root = ET.fromstring(raw)
    items = []
    for node in root.iter("item"):
        media = node.find(MEDIA_NS + "content")
        guid = (node.findtext("guid") or node.findtext("link") or "").strip()
        items.append(
            {
                "guid": guid,
                "title": plain(node.findtext("title")),
                "link": (node.findtext("link") or "").strip(),
                "summary": plain(node.findtext("description")),
                "category": (node.findtext("category") or "").strip(),
                "pubdate": (node.findtext("pubDate") or "").strip(),
                "image": media.get("url") if media is not None else None,
            }
        )
    return items


def load_state(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save_state(path, seen):
    path.write_text(json.dumps(seen[-500:], indent=1))


def to_iso(rfc822):
    from email.utils import parsedate_to_datetime

    try:
        return parsedate_to_datetime(rfc822).isoformat()
    except (TypeError, ValueError):
        return None


def build_embed(item):
    is_patch = bool(PATCH_WORDS.search(item["title"]))
    embed = {
        "title": item["title"][:256],
        "url": item["link"],
        "description": item["summary"][:500],
        "color": COLOR_PATCH if is_patch else COLOR_NEWS,
        "footer": {"text": "WoW Forever patch notes" if is_patch else "WoW Forever news"},
    }
    ts = to_iso(item["pubdate"])
    if ts:
        embed["timestamp"] = ts
    if item["image"]:
        embed["image"] = {"url": item["image"]}
    return embed


def post(webhook, item, retries=3):
    body = json.dumps({"embeds": [build_embed(item)]}).encode()
    req = urllib.request.Request(
        webhook,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    for attempt in range(retries):
        try:
            urllib.request.urlopen(req, timeout=30).read()
            return True
        except urllib.error.HTTPError as err:
            if err.code == 429:
                try:
                    wait = float(json.loads(err.read()).get("retry_after", 2))
                except Exception:
                    wait = 2.0
                time.sleep(wait + 0.5)
                continue
            print(f"discord rejected post ({err.code}) for {item['title']!r}", file=sys.stderr)
            return False
        except urllib.error.URLError as err:
            print(f"network error posting to discord: {err}", file=sys.stderr)
            time.sleep(2)
    return False


def run_once(args):
    try:
        items = parse_feed(fetch(args.feed))
    except (urllib.error.URLError, ET.ParseError, OSError) as err:
        print(f"could not read feed: {err}", file=sys.stderr)
        return

    if args.category:
        items = [i for i in items if i["category"].lower() == args.category.lower()]
    items = [i for i in items if i["guid"]]

    seen = load_state(args.state)
    if seen is None:
        # First run: mark everything currently in the feed as seen so the
        # channel does not get flooded with old posts.
        keep_back = items[: args.backfill]
        seen = [i["guid"] for i in items if i not in keep_back]
        print(f"first run: seeded {len(seen)} existing items, will announce {len(keep_back)}")
        if not args.dry_run:
            save_state(args.state, seen)
        new = keep_back
    else:
        known = set(seen)
        new = [i for i in items if i["guid"] not in known]

    # Feed is newest first, announce oldest first so the channel reads in order.
    for item in reversed(new):
        if args.dry_run:
            print(f"[dry run] {item['category']} | {item['title']} | {item['link']}")
            continue
        if post(args.webhook, item):
            seen.append(item["guid"])
            save_state(args.state, seen)
            time.sleep(1.2)
        else:
            print("stopping this run, will retry the rest next time", file=sys.stderr)
            break
    print(f"checked feed, {len(new)} new item(s)")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--feed", default=os.environ.get("FOREVER_FEED_URL", DEFAULT_FEED), help="RSS feed URL")
    p.add_argument("--webhook", default=os.environ.get("DISCORD_WEBHOOK_URL"), help="Discord webhook URL")
    p.add_argument("--state", type=Path, default=DEFAULT_STATE, help="file that remembers posted items")
    p.add_argument("--category", default="Forever", help="only post items with this feed category, empty for all")
    p.add_argument("--loop", type=int, default=0, help="seconds between checks, 0 runs once")
    p.add_argument("--backfill", type=int, default=0, help="on first run, announce this many latest items")
    p.add_argument("--dry-run", action="store_true", help="print new items without posting")
    args = p.parse_args()

    if not args.webhook and not args.dry_run:
        p.error("set DISCORD_WEBHOOK_URL or pass --webhook")

    if args.loop:
        while True:
            run_once(args)
            time.sleep(max(args.loop, 300))
    else:
        run_once(args)


if __name__ == "__main__":
    main()
