#!/usr/bin/env python3
"""Build the Yet I Will Rejoice site from data/episodes.json into _site/.

    python3 tools/build.py            # production build (pretty URLs)
    python3 tools/build.py --preview  # links point at index.html files, for previews
"""
import datetime as dt
import hashlib
import html
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"
SITE_URL = "https://yetiwillrejoice.org"
PREVIEW = "--preview" in sys.argv

FORM = "https://docs.google.com/forms/d/e/1FAIpQLSdp9v20gyJ-YPRBo8-JA6z_umQGF9Grcw8mrs4m2gZ3MpXygQ/viewform"
GIVE = "https://dareministries.breezechms.com/give/online?fund_id=1871299"
DARE = "https://www.dareministries.com/"
YOUTUBE = "https://www.youtube.com/@YetIWillRejoice"
YOUTUBE_SUB = "https://www.youtube.com/@YetIWillRejoice?sub_confirmation=1"
PLATFORMS = [
    ("YouTube", YOUTUBE_SUB),
    ("Spotify", "https://podcasters.spotify.com/pod/show/brandon-anderson261"),
    ("Apple Podcasts", "https://podcasts.apple.com/us/podcast/yet-i-will-rejoice/id1768112300"),
    ("Amazon Music", "https://music.amazon.com/podcasts/a5a6a9db-7e06-4aa9-a09c-adb388df9610/yet-i-will-rejoice"),
    ("iHeartRadio", "https://iheart.com/podcast/215405678/"),
    ("Castbox", "https://castbox.fm/ch/6283564"),
    ("Goodpods", "https://goodpods.app.link/DNbY0UQ3PMb"),
]
SOCIAL = [
    ("Instagram", "https://www.instagram.com/yetiwillrejoicepodcast/"),
    ("Facebook", "https://www.facebook.com/profile.php?id=61558877346229"),
    ("YouTube", YOUTUBE),
]
START_HERE = ["ome3eGuhMhY", "aYvLZUP68V0", "IG2kkExMWT8", "afMlbS0lxIU"]
HOST = "Brandon Anderson"

esc = html.escape
PLAY = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>'


def slugify(text):
    text = text.lower().replace("’", "").replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:70].rstrip("-")


def fmt_date(iso):
    if not iso:
        return ""
    d = dt.date.fromisoformat(iso[:10])
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def link(root, path):
    """Site-relative link. path is '' for home or 'episodes/' style."""
    if PREVIEW and (path == "" or path.endswith("/")):
        path += "index.html"
    return root + path if path else (root or "./")


def asset_hash(path):
    return hashlib.sha1((ROOT / path).read_bytes()).hexdigest()[:8]


# ---------------------------------------------------------------- data

def load():
    data = json.loads((ROOT / "data" / "episodes.json").read_text())
    series = {s["key"]: s for s in data["series"]}
    eps = [e for e in data["episodes"] if e["youtube"] not in set(data.get("ignore", [])) and not e.get("hidden")]
    seen = set()
    for e in eps:
        base = slugify(e["title"]) or e["youtube"].lower()
        slug, n = base, 2
        while slug in seen:
            slug, n = f"{base}-{n}", n + 1
        seen.add(slug)
        e["slug"] = e.get("slug") or slug
        e["series_name"] = series[e["series"]]["name"] if e.get("series") in series else ""
    # Newest first: by date when known, then by episode number.
    eps.sort(key=lambda e: (e.get("date") or "", e.get("number") or 0), reverse=True)
    for s in series.values():
        s["episodes"] = [e for e in eps if e.get("series") == s["key"]]
    return eps, series


def thumb(e, size="hqdefault"):
    return f"https://i.ytimg.com/vi/{e['youtube']}/{size}.jpg"


def ep_meta(e, with_series=True):
    bits = []
    if e.get("number"):
        bits.append(f"Ep. {e['number']}")
    if with_series and e.get("series_name"):
        bits.append(e["series_name"])
    if e.get("guest"):
        bits.append(f"with {e['guest']}")
    elif e.get("cohost"):
        bits.append(f"with {e['cohost']}")
    return " · ".join(esc(b) for b in bits)


def description_html(e):
    """YouTube descriptions, minus hashtags and timestamps lists, as paragraphs."""
    text = (e.get("description") or "").strip()
    if not text and e.get("guest"):
        return f"<p>{HOST} sits down with {esc(e['guest'])} to talk about {esc(e['title'][0].lower() + e['title'][1:])}.</p>"
    if not text:
        who = f"{HOST} and {e['cohost']}" if e.get("cohost") else (f"{HOST} and {e['guest']}" if e.get("guest") else HOST)
        verb = "takes" if who == HOST else "take"
        return f"<p>{esc(who)} {verb} on the question <em>{esc(e['title'])}</em> and open the Bible for an honest answer.</p>".replace("and open", "and opens" if who == HOST else "and open")
    lines = [ln for ln in text.splitlines() if not re.fullmatch(r"\s*(#\w+\s*)+", ln)]
    paras = re.split(r"\n\s*\n", "\n".join(lines).strip())
    out = []
    for p in paras:
        p = esc(p.strip())
        p = re.sub(r"(https?://[^\s<]+)", r'<a href="\1" target="_blank" rel="noopener">\1</a>', p)
        out.append("<p>" + p.replace("\n", "<br>") + "</p>")
    return "\n".join(out)


def excerpt(e, n=180):
    text = re.sub(r"https?://\S+|#\w+", "", e.get("description") or "").strip()
    text = re.split(r"\n\s*\n", text)[0].replace("\n", " ") if text else ""
    if not text and e.get("guest"):
        return f"{HOST} sits down with {e['guest']} to talk about {e['title'][0].lower() + e['title'][1:]}."
    if not text:
        return f"{HOST} answers the question “{e['title']}” from Scripture."
    return text if len(text) <= n else text[: n].rsplit(" ", 1)[0] + "…"


# ---------------------------------------------------------------- pieces

def card(e, root, extra_class=""):
    return f"""<a class="ep {extra_class}" href="{link(root, f'episodes/{e['slug']}/')}" data-series="{esc(e.get('series') or '')}" data-search="{esc((e['title'] + ' ' + e.get('series_name', '') + ' ' + (e.get('guest') or e.get('cohost') or '')).lower())}">
  <span class="ep-thumb"><img src="{thumb(e)}" alt="" loading="lazy" width="480" height="360"><span class="ep-play">{PLAY}</span></span>
  <span class="ep-title">{esc(e['title'])}</span>
  <span class="ep-meta">{ep_meta(e)}</span>
</a>"""


def video(e, eager=False):
    return f"""<div class="video" data-youtube="{e['youtube']}">
  <button type="button" aria-label="Play {esc(e['title'])}">
    <img src="{thumb(e, 'maxresdefault' if eager else 'hqdefault')}" onerror="this.onerror=null;this.src='{thumb(e)}'" alt="" {'' if eager else 'loading="lazy"'}>
    <span class="play">{PLAY}</span>
  </button>
</div>"""


def platform_list(cls="platforms"):
    items = "".join(f'<li><a href="{u}" target="_blank" rel="noopener">{esc(n)}</a></li>' for n, u in PLATFORMS)
    return f'<ul class="{cls}">{items}</ul>'


def subscribe_band(root):
    return f"""<section class="subscribe" id="subscribe" aria-labelledby="sub-title">
  <div class="wrap sub-grid">
    <div>
      <h2 id="sub-title">Never miss an episode.</h2>
      <p>New episodes most weeks. Follow on the app you already use and the next one will find you.</p>
    </div>
    {platform_list()}
  </div>
</section>"""


def ask_band(root):
    return f"""<section class="ask" aria-labelledby="ask-title">
  <div class="wrap ask-grid">
    <h2 id="ask-title">What’s the question you can’t shake?</h2>
    <div>
      <p>Send it in. We read every one, and many become episodes. You can stay anonymous.</p>
      <a class="btn btn-accent" href="{link(root, 'ask/')}">Ask your question</a>
    </div>
  </div>
</section>"""


def page(root, path, title, description, body, nav="", og_image=None, jsonld=None, page_class=""):
    full_title = title if title.startswith("Yet I Will Rejoice") else f"{title} · Yet I Will Rejoice"
    canonical = f"{SITE_URL}/{path}"
    og_image = og_image or f"{SITE_URL}/assets/img/og.png"
    css, js = asset_hash("assets/css/site.css"), asset_hash("assets/js/site.js")

    def nl(key, label, href):
        cur = ' aria-current="page"' if nav == key else ""
        return f'<a href="{href}"{cur}>{label}</a>'

    ld = f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>' if jsonld else ""
    socials = "".join(f'<li><a href="{u}" target="_blank" rel="noopener">{n}</a></li>' for n, u in SOCIAL)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Yet I Will Rejoice">
<meta property="og:title" content="{esc(full_title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{og_image}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#141311">
<link rel="icon" href="{root}assets/img/favicon.png">
<link rel="apple-touch-icon" href="{root}assets/img/favicon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Jost:wght@300;400;500;600&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&display=swap">
<link rel="stylesheet" href="{root}assets/css/site.css?v={css}">
{ld}
</head>
<body class="{page_class}">
<a class="skip" href="#main">Skip to content</a>
<header class="site-head">
  <div class="wrap head-row">
    <a class="brand" href="{link(root, '')}" aria-label="Yet I Will Rejoice home"><img src="{root}assets/img/logo-318-white.png" alt="" width="837" height="757"><span>Yet I Will Rejoice</span></a>
    <button class="menu-btn" type="button" aria-expanded="false" aria-controls="site-nav">Menu</button>
    <nav id="site-nav" class="site-nav" aria-label="Main">
      {nl('episodes', 'Episodes', link(root, 'episodes/'))}
      {nl('about', 'About', link(root, 'about/'))}
      {nl('ask', 'Ask a question', link(root, 'ask/'))}
      <a class="btn btn-small btn-light" href="#subscribe">Subscribe</a>
    </nav>
  </div>
</header>
<main id="main">
{body}
</main>
{subscribe_band(root)}
<footer class="site-foot">
  <div class="wrap foot-grid">
    <div class="foot-brand">
      <img src="{root}assets/img/logo-318-white.png" alt="Yet I Will Rejoice" width="837" height="757">
      <p>Honest answers to life’s hardest questions, from Scripture, pointing to Jesus.</p>
    </div>
    <div>
      <h2>Explore</h2>
      <ul>
        <li><a href="{link(root, 'episodes/')}">All episodes</a></li>
        <li><a href="{link(root, 'about/')}">About the show</a></li>
        <li><a href="{link(root, 'ask/')}">Ask a question</a></li>
        <li><a href="{GIVE}" target="_blank" rel="noopener">Support the show</a></li>
        <li><a href="{link(root, 'links/')}">All our links</a></li>
      </ul>
    </div>
    <div>
      <h2>Follow</h2>
      <ul>{socials}</ul>
    </div>
  </div>
  <div class="wrap foot-base">
    <p>A podcast from <a href="{DARE}" target="_blank" rel="noopener">Dare Ministries</a>, Colorado Springs.</p>
    <p>“Yet I will rejoice in the Lord.” Habakkuk 3:18</p>
  </div>
</footer>
<script src="{root}assets/js/site.js?v={js}" defer></script>
</body>
</html>
"""


# ---------------------------------------------------------------- pages

def home(eps, series):
    root = ""
    latest = eps[0]
    by_id = {e["youtube"]: e for e in eps}
    start = [by_id[i] for i in START_HERE if i in by_id]
    recent = [e for e in eps[1:] if e not in start][:6]
    series_cards = "".join(
        f"""<a class="series-card" href="{link(root, 'episodes/')}#{s['key']}">
  <span class="series-name">{esc(s['name'])}</span>
  <span class="series-blurb">{esc(s['blurb'])}</span>
  <span class="series-count">{len(s['episodes'])} episode{'s' if len(s['episodes']) != 1 else ''}</span>
</a>"""
        for s in series.values() if s["episodes"]
    )
    start_cards = "".join(
        f"""<li><a href="{link(root, f'episodes/{e['slug']}/')}"><span class="n">{i}</span><span class="t">{esc(e['title'])}</span><span class="m">{ep_meta(e)}</span></a></li>"""
        for i, e in enumerate(start, 1)
    )
    body = f"""
<section class="hero">
  <div class="wrap hero-grid">
    <img class="hero-logo" src="assets/img/logo-318-white.png" alt="3:18 Yet I Will Rejoice" width="837" height="757">
    <div class="hero-copy">
      <h1>Hard questions.<br>Honest answers.<br><span class="soft">A God worth rejoicing in.</span></h1>
      <p class="lede">Why is there so much pain? Can I trust God with my doubts? Each week {HOST} and a friend take one real question and answer it straight from the Bible.</p>
      <div class="btn-row">
        <a class="btn btn-accent" href="{link(root, f'episodes/{latest["slug"]}/')}">{PLAY}Watch the latest</a>
        <a class="btn btn-ghost" href="{YOUTUBE_SUB}" target="_blank" rel="noopener">Subscribe on YouTube</a>
      </div>
    </div>
  </div>
</section>

<section class="section latest" aria-labelledby="latest-title">
  <div class="wrap latest-grid">
    {video(latest, eager=True)}
    <div class="latest-copy">
      <h2 id="latest-title">{esc(latest['title'])}</h2>
      <p class="latest-meta"><span class="new-tag">Newest episode</span> {ep_meta(latest)}{(' · ' + fmt_date(latest.get('date'))) if latest.get('date') else ''}</p>
      <p>{esc(excerpt(latest, 260))}</p>
      <a class="text-link" href="{link(root, f'episodes/{latest["slug"]}/')}">Episode page and notes</a>
    </div>
  </div>
</section>

<section class="section start" aria-labelledby="start-title">
  <div class="wrap start-grid">
    <div>
      <h2 id="start-title">New here? Start with these four.</h2>
      <p class="lede">Where the show begins, and the questions people bring to it most.</p>
    </div>
    <ol class="start-list">{start_cards}</ol>
  </div>
</section>

<section class="section" aria-labelledby="recent-title">
  <div class="wrap">
    <div class="head-split">
      <h2 id="recent-title">Recent episodes</h2>
      <a class="text-link" href="{link(root, 'episodes/')}">All {len(eps)} episodes</a>
    </div>
    <div class="ep-grid">{''.join(card(e, root) for e in recent)}</div>
  </div>
</section>

<section class="section series-sec" aria-labelledby="series-title">
  <div class="wrap">
    <h2 id="series-title">Browse by series</h2>
    <div class="series-grid">{series_cards}</div>
  </div>
</section>

<section class="verse" aria-label="Habakkuk 3:17 to 18">
  <div class="wrap">
    <blockquote>
      <p>Though the fig tree should not blossom, nor fruit be on the vines, the produce of the olive fail and the fields yield no food… <strong>yet I will rejoice in the Lord;</strong> I will take joy in the God of my salvation.</p>
      <cite>Habakkuk 3:17–18</cite>
    </blockquote>
  </div>
</section>

<section class="section host" aria-labelledby="host-title">
  <div class="wrap host-grid">
    <img class="host-photo" src="assets/img/brandon.jpg" alt="{HOST}" width="250" height="374" loading="lazy">
    <div>
      <h2 id="host-title">Hosted by {HOST}, with a different friend at the table each week.</h2>
      <p>Brandon founded Dare Ministries in 2015 to prepare young believers for a lifetime of ministry. He is a youth pastor, leads a college ministry, and has spent years fielding the questions students are afraid to ask out loud. Yet I Will Rejoice is where he answers them.</p>
      <a class="text-link" href="{link(root, 'about/')}">About the show</a>
    </div>
  </div>
</section>

{ask_band(root)}
"""
    ld = {
        "@context": "https://schema.org", "@type": "PodcastSeries", "name": "Yet I Will Rejoice",
        "url": SITE_URL + "/", "description": "Honest answers to life’s hardest questions, from Scripture.",
        "author": {"@type": "Person", "name": HOST}, "publisher": {"@type": "Organization", "name": "Dare Ministries", "url": DARE},
        "sameAs": [u for _, u in PLATFORMS + SOCIAL],
    }
    return page("", "", "Yet I Will Rejoice · Honest answers to hard questions about God",
                "A weekly podcast taking life’s hardest questions about God, suffering, sin and faith, and answering them from Scripture. Hosted by Brandon Anderson.",
                body, og_image=thumb(latest, "maxresdefault"), jsonld=ld, page_class="home")


def episodes_page(eps, series):
    root = "../"
    chips = '<button type="button" class="chip" data-filter="all" aria-pressed="true">All</button>' + "".join(
        f'<button type="button" class="chip" data-filter="{s["key"]}" aria-pressed="false">{esc(s["name"])}</button>'
        for s in series.values() if s["episodes"]
    )
    body = f"""
<section class="page-head">
  <div class="wrap">
    <h1>Every episode</h1>
    <p class="lede">{len(eps)} conversations and counting. Search for your question, or pick a series.</p>
  </div>
</section>
<section class="section library" data-library>
  <div class="wrap">
    <div class="lib-tools">
      <label class="search"><span class="sr">Search episodes</span><input type="search" placeholder="Search episodes, like “anxiety” or “prayer”" data-search-input></label>
      <div class="chips" role="group" aria-label="Filter by series">{chips}</div>
    </div>
    <div class="ep-grid">{''.join(card(e, root) for e in eps)}</div>
    <p class="empty" hidden data-empty>No episode on that yet. <a href="{link(root, 'ask/')}">Ask it</a> and it might become one.</p>
  </div>
</section>
{ask_band(root)}
"""
    return page(root, "episodes/", "All episodes", "Every episode of Yet I Will Rejoice: honest, Scripture-first answers about God, sin, suffering, the Bible and living the Christian life.",
                body, nav="episodes")


def episode_page(e, eps, series):
    root = "../../"
    url = f"{SITE_URL}/episodes/{e['slug']}/"
    i = eps.index(e)
    newer = eps[i - 1] if i > 0 else None
    older = eps[i + 1] if i + 1 < len(eps) else None
    same = [x for x in eps if x is not e and e.get("series") and x.get("series") == e.get("series")][:3]
    if len(same) < 3:
        same += [x for x in eps if x is not e and x not in same][: 3 - len(same)]
    who = e.get("guest") or e.get("cohost")
    people = f"{HOST} with {who}" if who else HOST
    share_text = f"{e['title']} · Yet I Will Rejoice"
    from urllib.parse import quote
    pn = ""
    if newer or older:
        pn = '<nav class="prevnext" aria-label="More episodes">'
        if older:
            pn += f'<a class="prev" href="{link(root, f"episodes/{older["slug"]}/")}"><span>Previous</span>{esc(older["title"])}</a>'
        if newer:
            pn += f'<a class="next" href="{link(root, f"episodes/{newer["slug"]}/")}"><span>Next</span>{esc(newer["title"])}</a>'
        pn += "</nav>"
    series_link = (f'<a href="{link(root, "episodes/")}#{e["series"]}">{esc(e["series_name"])}</a>' if e.get("series_name") else "")
    meta = " · ".join(b for b in [f"Episode {e['number']}" if e.get("number") else "", series_link, fmt_date(e.get("date"))] if b)
    body = f"""
<article class="episode">
  <header class="ep-head">
    <div class="wrap narrow">
      <a class="back" href="{link(root, 'episodes/')}">All episodes</a>
      <h1>{esc(e['title'])}</h1>
      <p class="ep-people">{esc(people)}</p>
      <p class="ep-head-meta">{meta}</p>
    </div>
  </header>
  <div class="wrap mid">{video(e, eager=True)}</div>
  <div class="wrap narrow ep-body">
    <div class="ep-listen">
      <a class="btn btn-accent" href="https://www.youtube.com/watch?v={e['youtube']}" target="_blank" rel="noopener">Watch on YouTube</a>
      <details class="listen-more">
        <summary class="btn btn-ghost-dark">Listen on another app</summary>
        {platform_list("platforms compact")}
      </details>
    </div>
    <div class="prose">{description_html(e)}</div>
    <div class="share" data-share data-url="{url}" data-title="{esc(share_text)}">
      <h2>Know someone asking this?</h2>
      <div class="share-row">
        <button type="button" class="btn btn-ghost-dark" data-share-native hidden>Share</button>
        <button type="button" class="btn btn-ghost-dark" data-copy>Copy link</button>
        <a class="btn btn-ghost-dark" href="sms:?&body={quote(share_text + ' ' + url)}">Text it</a>
        <a class="btn btn-ghost-dark" href="https://www.facebook.com/sharer/sharer.php?u={quote(url)}" target="_blank" rel="noopener">Facebook</a>
        <a class="btn btn-ghost-dark" href="mailto:?subject={quote(share_text)}&body={quote(url)}">Email</a>
      </div>
    </div>
    {pn}
  </div>
</article>
<section class="section more" aria-labelledby="more-title">
  <div class="wrap">
    <h2 id="more-title">{'More from ' + esc(e['series_name']) if e.get('series_name') else 'Keep watching'}</h2>
    <div class="ep-grid">{''.join(card(x, root) for x in same)}</div>
  </div>
</section>
{ask_band(root)}
"""
    ld = {
        "@context": "https://schema.org", "@type": "PodcastEpisode", "name": e["title"], "url": url,
        "description": excerpt(e, 300), "partOfSeries": {"@type": "PodcastSeries", "name": "Yet I Will Rejoice", "url": SITE_URL + "/"},
        "associatedMedia": {"@type": "VideoObject", "name": e["title"], "embedUrl": f"https://www.youtube.com/embed/{e['youtube']}",
                            "thumbnailUrl": thumb(e, "maxresdefault"), "description": excerpt(e, 300)},
    }
    if e.get("number"):
        ld["episodeNumber"] = e["number"]
    if e.get("date"):
        ld["datePublished"] = e["date"]
        ld["associatedMedia"]["uploadDate"] = e["date"]
    return page(root, f"episodes/{e['slug']}/", e["title"], excerpt(e, 155), body, nav="episodes",
                og_image=thumb(e, "maxresdefault"), jsonld=ld)


def about_page():
    root = "../"
    crew = [
        ("Brandon Anderson", "Host"), ("Daniel Clay", "Production Manager"), ("Jack Lupton", "Project Manager"),
        ("Joseph Dugan", "Operations Coordinator"), ("Caroline Anderson", "Design Manager"), ("Dannie Doyle", "Digital Media Coordinator"),
        ("Olivia Dugan", "Operations"), ("Tabby Ludwig", "Operations"), ("Annika Keown", "Operations"), ("Laura Clay", "Communications"),
        ("Michelle Townsend", "Communications"), ("Claire Floring", "Social Media"), ("Riley Sevier", "Social Media"),
        ("Caitlin Glaze", "Website Design"), ("Elijah Doyle", "Music"),
    ]
    crew_html = "".join(f"<li><b>{esc(n)}</b><span>{esc(r)}</span></li>" for n, r in crew)
    body = f"""
<section class="page-head">
  <div class="wrap">
    <h1>About the show</h1>
    <p class="lede">Regardless of life’s questions, challenges and obstacles, we can know God and rejoice in Him.</p>
  </div>
</section>
<section class="section">
  <div class="wrap narrow prose big">
    <p>Why is there so much pain? Where is God when life falls apart? Can I trust Him with my doubts? <em>Yet I Will Rejoice</em> takes on the hard questions of life in a broken world, one at a time, and keeps pointing to Jesus, who brings healing and redemption.</p>
    <p>Episodes are short, honest and Scripture-first. No question is off limits, and many of them come straight from listeners.</p>
  </div>
</section>
<section class="section why" aria-labelledby="why-title">
  <div class="wrap">
    <h2 id="why-title">Why Habakkuk?</h2>
    <p class="lede">The show’s name comes from a three-chapter book where a prophet brings his hardest questions straight to God.</p>
    <ol class="hab">
      <li><span class="ref">1:1–4</span><h3>The question</h3><p>“O Lord, how long shall I cry, and You will not hear?” Habakkuk looks at violence and injustice all around him and asks why God seems silent.</p></li>
      <li><span class="ref">1:5–6</span><h3>The answer</h3><p>God answers, though not the way Habakkuk expects. He is already at work, doing something Habakkuk “would not believe, though it were told.”</p></li>
      <li><span class="ref">3:17–19</span><h3>The response</h3><p>Nothing about his circumstances has changed, yet Habakkuk ends in worship: “Yet I will rejoice in the Lord.” That is the heart of the show.</p></li>
    </ol>
  </div>
</section>
<section class="section host" aria-labelledby="host-title">
  <div class="wrap host-grid">
    <img class="host-photo" src="{root}assets/img/brandon.jpg" alt="{HOST}" width="250" height="374" loading="lazy">
    <div>
      <h2 id="host-title">Meet your host</h2>
      <p>{HOST} founded Dare Ministries in 2015 to prepare young believers for a lifetime of ministry and to unite the body of Christ through partnerships on youth conferences. A 2016 Bob Jones University history graduate, he serves as a youth pastor and outreach director at a local church and leads a college ministry.</p>
      <p>Every episode he is joined by someone different: pastors, students, missionaries and friends of the show, each bringing their own story to the question.</p>
    </div>
  </div>
</section>
<section class="section crew-sec" aria-labelledby="crew-title">
  <div class="wrap">
    <div class="head-split">
      <h2 id="crew-title">The team behind the mic</h2>
      <p>Fifteen volunteers plan, record, design and share every episode.</p>
    </div>
    <ul class="crew">{crew_html}</ul>
  </div>
</section>
<section class="section dare">
  <div class="wrap narrow dare-note">
    <p><em>Yet I Will Rejoice</em> is a podcast from <a href="{DARE}" target="_blank" rel="noopener">Dare Ministries</a>, which equips young believers through conferences, college ministry and missions. If the show has helped you, you can <a href="{GIVE}" target="_blank" rel="noopener">support it here</a>.</p>
  </div>
</section>
{ask_band(root)}
"""
    return page(root, "about/", "About the show", "Why a podcast named for Habakkuk 3:18, who hosts it, and the volunteer team behind Yet I Will Rejoice.",
                body, nav="about")


def ask_page():
    root = "../"
    body = f"""
<section class="page-head">
  <div class="wrap">
    <h1>Ask your question</h1>
    <p class="lede">Doubts, hurts, hot topics, something a friend asked you that you couldn’t answer. Send it in. We read every one, and many become episodes.</p>
  </div>
</section>
<section class="section ask-form">
  <div class="wrap narrow">
    <div class="form-frame">
      <iframe src="{FORM}?embedded=true" title="Question form" loading="lazy">Loading the form…</iframe>
    </div>
    <p class="small">Form not loading? <a href="{FORM}" target="_blank" rel="noopener">Open it in a new tab</a>.</p>
  </div>
</section>
"""
    return page(root, "ask/", "Ask a question", "Send Yet I Will Rejoice the question about God, faith or the Bible you can’t shake. Many become episodes.",
                body, nav="ask")


def links_page(eps):
    """Link-in-bio page for Instagram and TikTok profiles, in place of Linktree."""
    root = "../"
    latest = eps[0]
    rows = [
        ("Newest episode: " + latest["title"], link(root, f"episodes/{latest['slug']}/"), "feature"),
        ("Ask a question", link(root, "ask/"), ""),
        ("Browse every episode", link(root, "episodes/"), ""),
    ] + [(f"Listen on {n}" if n != "YouTube" else "Subscribe on YouTube", u, "") for n, u in PLATFORMS] + [
        ("Support the show", GIVE, ""),
    ] + [(n, u, "social") for n, u in SOCIAL if n != "YouTube"]
    items = "".join(
        f'<li class="{c}"><a href="{u}"{"" if u.startswith(root) else " target=\"_blank\" rel=\"noopener\""}>{esc(t)}</a></li>'
        for t, u, c in rows
    )
    css = asset_hash("assets/css/site.css")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Yet I Will Rejoice · Links</title>
<meta name="description" content="Listen, subscribe, ask a question and follow Yet I Will Rejoice.">
<link rel="canonical" href="{SITE_URL}/links/">
<meta property="og:title" content="Yet I Will Rejoice">
<meta property="og:description" content="Listen, subscribe, ask a question and follow Yet I Will Rejoice.">
<meta property="og:image" content="{SITE_URL}/assets/img/og.png">
<meta name="theme-color" content="#141311">
<link rel="icon" href="{root}assets/img/favicon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Jost:wght@300;400;500;600&family=Newsreader:ital,opsz,wght@0,6..72,400;1,6..72,400&display=swap">
<link rel="stylesheet" href="{root}assets/css/site.css?v={css}">
</head>
<body class="links-page">
<main class="links">
  <a class="links-logo" href="{link(root, '')}"><img src="{root}assets/img/logo-318-white.png" alt="Yet I Will Rejoice" width="837" height="757"></a>
  <h1>Hard questions. Honest answers.</h1>
  <p>A weekly podcast with {HOST}, answering life’s hardest questions from Scripture.</p>
  <ul>{items}</ul>
  <p class="links-foot"><a href="{link(root, '')}">yetiwillrejoice.org</a> · A podcast from <a href="{DARE}" target="_blank" rel="noopener">Dare Ministries</a></p>
</main>
</body>
</html>
"""


def not_found():
    root = "/" if not PREVIEW else ""
    body = f"""
<section class="page-head center">
  <div class="wrap">
    <h1>That page isn’t here.</h1>
    <p class="lede">But the question you came with might be.</p>
    <div class="btn-row center"><a class="btn btn-accent" href="{root}episodes/">Browse episodes</a><a class="btn btn-ghost-dark" href="{root}ask/">Ask a question</a></div>
  </div>
</section>
"""
    return page(root, "404.html", "Page not found", "This page could not be found.", body)


# ---------------------------------------------------------------- build

def write(rel, text):
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def main():
    eps, series = load()
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "assets", OUT / "assets")
    write("index.html", home(eps, series))
    write("episodes/index.html", episodes_page(eps, series))
    for e in eps:
        write(f"episodes/{e['slug']}/index.html", episode_page(e, eps, series))
    write("about/index.html", about_page())
    write("ask/index.html", ask_page())
    write("links/index.html", links_page(eps))
    write("404.html", not_found())
    urls = ["", "episodes/", "about/", "ask/"] + [f"episodes/{e['slug']}/" for e in eps]
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f"  <url><loc>{SITE_URL}/{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
    if (ROOT / "CNAME").exists():
        shutil.copy(ROOT / "CNAME", OUT / "CNAME")
    write(".nojekyll", "")
    print(f"built {len(eps)} episodes into {OUT}")


if __name__ == "__main__":
    main()
