#!/usr/bin/env python3
"""Pull new episodes from the Yet I Will Rejoice YouTube channel into data/episodes.json.

Runs daily from .github/workflows/deploy.yml. It needs no API key: it reads the
channel's public RSS feed (the 15 most recent uploads), skips Shorts, and fills in
the description, date and co-host for any episode that is missing them.

Hand edits in episodes.json always win: the script only adds new episodes and
fills empty fields. To hide a video from the site, add its YouTube id to "ignore".
"""
import html
import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

HANDLE = "@YetIWillRejoice"
FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
DATA = Path(__file__).resolve().parent.parent / "data" / "episodes.json"
HOST = "Brandon Anderson"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Cookie": "CONSENT=YES+1; SOCS=CAI",
}
NS = {
    "a": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}

# New uploads get a series from their title; anything unmatched shows under "All episodes".
SERIES_RULES = [
    (r"armou?r of god", "armor"),
    (r"\bis\b.*\b(a )?sin(ful)?\b|\bsin\b", "sin"),
    (r"mormon|jehovah|islam|muslim|catholic|atheis|worldview|world view", "worldview"),
    (r"bible|gospel|testament", "bible"),
    (r"god exist|evil|suffer|bad things|resurrection|is jesus god|science", "apologetics"),
    (r"trinity|holy spirit|church\?|salvation|image of god|why did jesus|death penalty", "doctrine"),
]

COHOST_PATTERNS = [
    r"(?i:co-?host(?:ed)?(?: by)?|guests?|joined by|special guest)\s*[:\-–]?\s*((?:[A-Z][a-zA-Z'’\-]+ ?){2,3})",
    r"\bBrandon(?: Anderson)? (?:and|&|with) ((?:[A-Z][a-zA-Z'’\-]+ ?){1,3})",
    r"\bwith ((?:[A-Z][a-zA-Z'’\-]+ ?){2,3})",
]


NOT_NAMES = {"Jesus", "Christ", "God", "Lord", "Holy", "Spirit", "Bible", "Scripture", "Yet", "Will", "Rejoice", "Dare", "Ministries", "The"}


def fetch(url, method="GET"):
    req = urllib.request.Request(url, headers=UA, method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def is_short(vid):
    """youtube.com/shorts/<id> answers 200 for a Short and redirects for a normal video."""
    opener = urllib.request.build_opener(NoRedirect)
    try:
        r = opener.open(urllib.request.Request(f"https://www.youtube.com/shorts/{vid}", headers=UA, method="HEAD"), timeout=20)
        return r.status == 200
    except Exception:
        return False


def channel_id():
    """Look up the channel id behind the @handle, so the feed is always the podcast's own channel."""
    page = fetch(f"https://www.youtube.com/{HANDLE}")
    for pattern in (r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"',
                    r'"externalId":"(UC[\w-]{22})"', r'"channelId":"(UC[\w-]{22})"'):
        m = re.search(pattern, page)
        if m:
            return m.group(1)
    raise RuntimeError(f"no channel id found on the {HANDLE} page ({len(page)} bytes)")


def watch_details(vid):
    """Description and publish date from the watch page, or {} if YouTube won't say."""
    try:
        page = fetch(f"https://www.youtube.com/watch?v={vid}")
    except Exception as e:
        print(f"  watch page failed for {vid}: {e}", file=sys.stderr)
        return {}
    out = {}
    m = re.search(r'"shortDescription":("(?:[^"\\]|\\.)*")', page)
    if m:
        out["description"] = json.loads(m.group(1))
    else:
        print(f"  no description on watch page for {vid} ({len(page)} bytes)", file=sys.stderr)
    m = re.search(r'"(?:publishDate|uploadDate)":"(\d{4}-\d{2}-\d{2})', page)
    if m:
        out["date"] = m.group(1)
    m = re.search(r'<meta name="title" content="([^"]*)"', page)
    if m:
        out["title"] = html.unescape(m.group(1))
    return out


def guess_series(title):
    t = title.lower()
    for pattern, key in SERIES_RULES:
        if re.search(pattern, t):
            return key
    return None


def guess_cohost(description):
    for pattern in COHOST_PATTERNS:
        for m in re.finditer(pattern, description or ""):
            name = m.group(1).strip()
            if name and not name.startswith("Brandon") and not NOT_NAMES & set(name.split()):
                return name
    return None


def guess_number(title, description):
    m = re.search(r"(?:\bEp(?:isode)?\.?\s*|#)(\d{1,3})\b", f"{title}\n{description or ''}", re.I)
    return int(m.group(1)) if m else None


def clean_title(title):
    title = re.sub(r"\s*[|\-–]\s*Yet I Will Rejoice.*$", "", title, flags=re.I)
    title = re.sub(r"\s*#\w+", "", title)
    return title.strip()


def main():
    data = json.loads(DATA.read_text())
    episodes = data["episodes"]
    by_id = {e["youtube"]: e for e in episodes}
    ignore = set(data.get("ignore", []))
    changed = False

    try:
        cid = channel_id()
        print(f"{HANDLE} is channel {cid}")
        root = ET.fromstring(fetch(FEED.format(cid)))
    except Exception as e:
        print(f"Could not read the YouTube feed: {e}", file=sys.stderr)
        return 0

    for entry in root.findall("a:entry", NS):
        vid = entry.findtext("yt:videoId", namespaces=NS)
        if not vid or vid in ignore:
            continue
        title = entry.findtext("a:title", namespaces=NS) or ""
        date = (entry.findtext("a:published", namespaces=NS) or "")[:10]
        desc = entry.findtext("media:group/media:description", namespaces=NS) or ""

        ep = by_id.get(vid)
        if ep is None:
            if "#short" in title.lower() or is_short(vid):
                data.setdefault("ignore", []).append(vid)
                ignore.add(vid)
                changed = True
                print(f"skip short {vid}: {title}")
                continue
            ep = {"youtube": vid, "title": clean_title(title), "series": guess_series(title)}
            n = guess_number(title, desc)
            if n:
                ep["number"] = n
            episodes.insert(0, ep)
            by_id[vid] = ep
            changed = True
            print(f"new episode {vid}: {ep['title']}")
        for key, value in (("date", date), ("description", desc)):
            if value and not ep.get(key):
                ep[key] = value
                changed = True
        if not ep.get("cohost") and ep.get("series") != "guest":
            c = guess_cohost(ep.get("description"))
            if c:
                ep["cohost"] = c
                changed = True

    # Older episodes fall out of the 15-item feed; fill their gaps from the watch page.
    for ep in episodes:
        if ep.get("description") and ep.get("date"):
            continue
        info = watch_details(ep["youtube"])
        for key in ("description", "date"):
            if info.get(key) and not ep.get(key):
                ep[key] = info[key]
                changed = True
        if not ep.get("cohost") and ep.get("series") != "guest":
            c = guess_cohost(ep.get("description"))
            if c:
                ep["cohost"] = c
                changed = True

    if changed:
        DATA.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        print("episodes.json updated")
    else:
        print("no changes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
