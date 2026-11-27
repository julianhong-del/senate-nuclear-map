#!/usr/bin/env python3
"""Build news.json for the Senate Nuclear Map News tab.

Runs daily in GitHub Actions (see .github/workflows/news.yml). Standard library only.
Sources: Google News RSS queries (reliable, no key) plus a few trade/agency feeds when reachable.
Output: news.json = {"generated": ISO-UTC, "items": [{title, link, source, date, topic, summary, person_id}]}
"""
import json, re, sys, html, hashlib, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

ROOT = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))
PEOPLE = f"{ROOT}/people.json"
OUT = f"{ROOT}/news.json"
DAYS = 14
UA = "Mozilla/5.0 (compatible; SenateNuclearMap/1.0; +https://github.com)"

TOPIC_QUERIES = [
    ("Enrichment & HALEU", '"uranium enrichment" OR HALEU OR "high-assay low-enriched uranium" OR Centrus OR Urenco OR "General Matter" OR "Global Laser Enrichment" OR Orano'),
    ("NRC & licensing", '"Nuclear Regulatory Commission" (license OR licensing OR rule OR approval)'),
    ("DOE & policy", '"Department of Energy" (nuclear fuel OR HALEU OR enrichment OR "advanced reactor")'),
    ("Reactors & projects", '"small modular reactor" OR "advanced reactor" OR microreactor OR "nuclear plant" (approval OR construction OR restart OR contract)'),
    ("Fuel supply & markets", '"Russian uranium" OR "uranium imports" OR "nuclear fuel supply" OR "uranium price" OR "conversion services"'),
]
DIRECT_FEEDS = [
    ("World Nuclear News", "https://www.world-nuclear-news.org/rss", "Reactors & projects"),
    ("ANS Nuclear Newswire", "https://www.ans.org/news/rss/", "Reactors & projects"),
    ("NRC news releases", "https://www.nrc.gov/public-involve/rss.xml", "NRC & licensing"),
]
KEYWORDS = [  # re-tag by content so items land in the most specific bucket
    ("Enrichment & HALEU", r"enrich|haleu|centrus|urenco|orano|general matter|laser enrichment|paducah|piketon|centrifuge"),
    ("NRC & licensing", r"\bnrc\b|nuclear regulatory|license|licensing|environmental impact statement"),
    ("Fuel supply & markets", r"russian uranium|uranium import|tenex|rosatom|uranium price|spot price|conversion|fuel supply"),
    ("DOE & policy", r"department of energy|\bdoe\b|secretary wright|appropriations|senate|house|congress|executive order"),
    ("Reactors & projects", r"reactor|smr|plant|restart|construction|terrapower|x-energy|oklo|kairos|nuscale|westinghouse"),
]


def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def parse_feed(raw, default_source):
    items = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return items
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        pub = it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date") or ""
        desc = it.findtext("description") or ""
        src = it.findtext("source") or default_source
        items.append((title, link, pub, desc, src))
    for e in root.findall(".//atom:entry", ns):
        title = (e.findtext("atom:title", default="", namespaces=ns) or "").strip()
        link_el = e.find("atom:link", ns)
        link = link_el.get("href") if link_el is not None else ""
        pub = e.findtext("atom:updated", default="", namespaces=ns) or e.findtext("atom:published", default="", namespaces=ns) or ""
        desc = e.findtext("atom:summary", default="", namespaces=ns) or ""
        items.append((title, link, pub, desc, default_source))
    return items


def clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def to_iso(pub):
    if not pub:
        return ""
    try:
        d = parsedate_to_datetime(pub)
    except Exception:
        try:
            d = datetime.fromisoformat(pub.replace("Z", "+00:00"))
        except Exception:
            return ""
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).isoformat()


def gnews(query, when_days=DAYS):
    q = urllib.parse.quote(f"{query} when:{when_days}d")
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def main():
    people = {}
    try:
        people = json.load(open(PEOPLE, encoding="utf-8"))
    except Exception as e:
        print("warn: people.json not readable:", e, file=sys.stderr)
    cutoff = datetime.now(timezone.utc) - timedelta(days=DAYS)
    seen = set()
    out = []

    def add(title, link, pub, desc, src, topic, person_id=""):
        title = clean(title)
        if not title or not link:
            return
        # Google News wraps the title as "Headline - Source"
        if " - " in title and not src:
            title, src = title.rsplit(" - ", 1)
        key = hashlib.sha1(re.sub(r"\W+", "", title.lower())[:80].encode()).hexdigest()
        if key in seen:
            return
        iso = to_iso(pub)
        if iso and datetime.fromisoformat(iso) < cutoff:
            return
        seen.add(key)
        text = (title + " " + clean(desc)).lower()
        final_topic = topic
        if not person_id:
            for t, pat in KEYWORDS:
                if re.search(pat, text):
                    final_topic = t
                    break
        out.append({"title": title, "link": link, "source": clean(src) or "", "date": iso, "topic": final_topic, "summary": clean(desc)[:300], "person_id": person_id})

    # topic queries
    for topic, q in TOPIC_QUERIES:
        try:
            for title, link, pub, desc, src in parse_feed(fetch(gnews(q)), ""):
                add(title, link, pub, desc, src, topic)
        except Exception as e:
            print(f"warn: topic query failed ({topic}): {e}", file=sys.stderr)
    # direct feeds (best effort)
    for name, url, topic in DIRECT_FEEDS:
        try:
            for title, link, pub, desc, src in parse_feed(fetch(url), name):
                add(title, link, pub, desc, name, topic)
        except Exception as e:
            print(f"warn: feed failed ({name}): {e}", file=sys.stderr)
    # priority senators in the news
    sens = [p for p in people.get("people", []) if p.get("kind") == "senator" and int(p.get("priority", 0)) >= 5]
    for p in sens:
        last = p["name"].split()[-1]
        q = f'"Senator {last}" OR "Sen. {last}" (nuclear OR uranium OR energy OR reactor)'
        try:
            for title, link, pub, desc, src in parse_feed(fetch(gnews(q, 10)), ""):
                add(title, link, pub, desc, src, "Senators in the news", p["id"])
        except Exception as e:
            print(f"warn: senator query failed ({last}): {e}", file=sys.stderr)

    out.sort(key=lambda x: x.get("date", ""), reverse=True)
    if len(out) < 5:
        print("error: fewer than 5 items collected; keeping the previous news.json", file=sys.stderr)
        sys.exit(2)
    json.dump({"generated": datetime.now(timezone.utc).isoformat(timespec="minutes"), "days": DAYS, "items": out[:400]}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"wrote {OUT}: {len(out)} items")


if __name__ == "__main__":
    main()
