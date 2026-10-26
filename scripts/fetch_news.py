"""Henter nyheter til infoskjermen og skriver news.json.

Kjøres av GitHub-jobben hvert 15. minutt. Bruker bare Pythons standardbibliotek.
Kilder og selskaper endres i FEEDS og COMPANIES under.
"""
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

BORS = {"tag": "Oslo Børs", "cls": "t-bors", "weight": 3, "days": 7, "max": 10}
COMPANIES = ["DOF", "Moreld", "BW Energy", "BW Offshore", "Equinor", "Aker BP", "Vår Energi", "Aker Solutions",
             "Subsea 7", "Subsea7", "Reach Subsea", "Odfjell", "Solstad", "Havila Shipping", "Eidesvik", "Siem Offshore",
             "Okea", "DNO", "Panoro", "TGS", "Archer", "Borr Drilling", "Seadrill", "Shelf Drilling", "Northern Ocean", "Akastor"]

# region: True = merkes Norden/Afrika/Globalt ut fra teksten. only_offshore: True = bare offshore-relaterte saker.
FEEDS = [
    {"name": "Offshore Energy", "weight": 2, "region": True,
     "url": "https://www.offshore-energy.biz/feed/"},
    {"name": "gCaptain Offshore", "weight": 2, "region": True,
     "url": "https://gcaptain.com/category/offshore-news/feed/"},
    {"name": "Splash247", "weight": 1, "region": True, "only_offshore": True,
     "url": "https://splash247.com/feed/"},
    {"name": "Subsea Norden", "weight": 2, "region": True,
     "url": "https://news.google.com/rss/search?q=subsea+(Norway+OR+%22North+Sea%22+OR+Equinor+OR+Barents)+when:7d&hl=en&gl=NO&ceid=NO:en"},
    {"name": "Subsea Afrika", "weight": 2, "region": True,
     "url": "https://news.google.com/rss/search?q=subsea+(Africa+OR+Angola+OR+Nigeria+OR+Mozambique+OR+Namibia+OR+Ghana)+when:7d&hl=en&gl=US&ceid=US:en"},
    {"name": "NRK Trøndelag", "tag": "Trøndelag", "cls": "t-trond", "weight": 1, "max": 4,
     "url": "https://www.nrk.no/trondelag/toppsaker.rss"},
    {"name": "NRK", "tag": "Norge", "cls": "t-norge", "weight": 1, "max": 4,
     "url": "https://www.nrk.no/toppsaker.rss"},
]

OFFSHORE = re.compile(r"subsea|offshore|fpso|\brigs?\b|drill|\boil\b|\bgas\b|\bROV\b|vessel|\bPSV\b|AHTS|pipeline|LNG|field|reservoir|platform|Equinor|Aker BP|Vår Energi|DOF|Moreld|BW Energy|TechnipFMC|Subsea ?7|Saipem|Oceaneering|North Sea|Nordsjø", re.I)
AFRICA = re.compile(r"Africa|Afrika|Angola|Nigeria|Mozambique|Namibia|Ghana|Senegal|Egypt|Ivory Coast|Côte d.Ivoire|Congo|Gabon|Cameroon|Tanzania|Mauritania|Equatorial Guinea|Libya|Algeria", re.I)
NORDIC = re.compile(r"Norw|Norge|North Sea|Nordsjø|Barents|Denmark|Danish|Iceland|Faroe|Sweden|Swedish|Finland|Equinor|Aker BP|Vår Energi|Okea|Hammerfest|Bergen|Stavanger|Trondheim", re.I)
# Stricter test for broad shipping feeds, where "oil" or "gas" alone usually means tankers
OFFSHORE_STRICT = re.compile(r"subsea|offshore|fpso|\brigs?\b|drill|\bROV\b|\bPSV\b|AHTS|\bCSV\b|\bIMR\b|platform|field development|Equinor|Aker BP|Vår Energi|DOF|Moreld|BW Energy|BW Offshore|TechnipFMC|Subsea ?7|Saipem|Oceaneering|North Sea|Nordsjø", re.I)
MEDIA = "{http://search.yahoo.com/mrss/}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}encoded"
UA = "Mozilla/5.0 (infoskjerm; +https://github.com)"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def strip(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def first_img(s):
    m = re.search(r"<img[^>]+src=[\"']([^\"']+)", s or "", re.I)
    return m.group(1) if m else ""


def iso(d):
    return d.astimezone(timezone.utc).isoformat()


def load_feed(f):
    root = ET.fromstring(get(f["url"]))
    out = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        source = it.findtext("source") or ""
        if not source and "news.google" in f["url"]:
            m = re.search(r" - ([^-]{2,40})$", title)
            if m:
                source, title = m.group(1), title[:m.start()]
        source = source or f["name"]
        if title.endswith(" - " + source):
            title = title[: -(len(source) + 3)]
        desc = it.findtext("description") or ""
        summary = strip(desc)
        if summary.startswith(title):
            summary = ""
        media = it.find(MEDIA + "content")
        if media is None:
            media = it.find(MEDIA + "thumbnail")
        enc = it.find("enclosure")
        img = (media.get("url") if media is not None else "") or \
              (enc.get("url") if enc is not None and (enc.get("type") or "").startswith("image") else "") or \
              first_img(it.findtext(CONTENT)) or first_img(desc)
        try:
            date = parsedate_to_datetime(it.findtext("pubDate"))
        except Exception:
            date = datetime.now(timezone.utc)
        text = title + " " + summary
        tag, cls, weight = f.get("tag"), f.get("cls"), f["weight"]
        if f.get("region"):
            if AFRICA.search(text):
                tag, cls, weight = "Offshore · Afrika", "t-afrika", weight + 1
            elif NORDIC.search(text):
                tag, cls, weight = "Offshore · Norden", "t-norden", weight + 1
            else:
                tag, cls = "Offshore · Globalt", "t-global"
        if f.get("only_offshore") and not OFFSHORE_STRICT.search(text):
            continue
        out.append({"tag": tag, "cls": cls, "weight": weight, "title": title, "source": source,
                    "summary": summary[:260], "img": img if img.startswith("http") else "", "date": iso(date)})
        if len(out) >= f.get("max", 8):
            break
    return out


def load_bors():
    today = datetime.now(timezone.utc).date()
    q = urllib.parse.urlencode({"category": "", "issuer": "", "market": "", "messageTitle": "",
                                "fromDate": str(today - timedelta(days=BORS["days"])), "toDate": str(today)})
    url = "https://api3.oslo.oslobors.no/v1/newsreader/list?" + q
    try:
        data = json.loads(get(url))
    except urllib.error.HTTPError as e:
        if e.code != 405:
            raise
        req = urllib.request.Request(url, data=b"", method="POST", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
    msgs = (data.get("data") or {}).get("messages") or data.get("messages") or []
    want = re.compile(r"\b(" + "|".join(re.escape(c) for c in COMPANIES) + r")\b", re.I)
    out = []
    for m in msgs:
        name, title = m.get("issuerName") or "", m.get("title") or ""
        if not (want.search(name) or want.search(title)):
            continue
        out.append({"tag": BORS["tag"], "cls": BORS["cls"], "weight": BORS["weight"] + (1 if AFRICA.search(name + title) else 0),
                    "title": title, "source": name or m.get("issuerSign") or "Oslo Børs", "summary": "", "img": "",
                    "date": m.get("publishedTime") or iso(datetime.now(timezone.utc))})
        if len(out) >= BORS["max"]:
            break
    return out


def main():
    items, failed = [], []
    for name, fn in [("Oslo Børs", load_bors)] + [(f["name"], lambda f=f: load_feed(f)) for f in FEEDS]:
        try:
            got = fn()
            print(f"{name}: {len(got)} saker")
            items += got
        except Exception as e:
            print(f"{name}: FEIL {e}", file=sys.stderr)
            failed.append(name)
    seen, unique = set(), []
    for n in items:
        if n["title"] and n["title"] not in seen:
            seen.add(n["title"])
            unique.append(n)
    with open("news.json", "w", encoding="utf-8") as fh:
        json.dump({"updated": iso(datetime.now(timezone.utc)), "sources": 1 + len(FEEDS), "failed": failed,
                   "items": unique}, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
