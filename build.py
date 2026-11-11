#!/usr/bin/env python3
"""Build ianadams.media from the Obsidian vault.

Usage:  python3 build.py [path/to/IanAdams.media]

Reads the markdown in the vault folder and writes a static site to ./public,
styled with the Fjord brand. Images are resized to WebP in public/img.
"""
import datetime as dt
import html
import json
import re
import shutil
import sys
from pathlib import Path

import markdown
import yaml
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "Ian Remote Vault" / "2 - Areas" / "Sites" / "IanAdams.media"
OUT = ROOT / "public"
IMG_OUT = OUT / "img"
SITE_URL = "https://ianadams.media"
YEAR = dt.date.today().year
MAX_W = 1600

STRAP = "Media that earns its place."
TITLE = "Digital Business Director"

# Small copy fixes applied to vault text when it is published (typos and
# testimonial job titles that were cut off when they were pasted in).
FIXES = [
    ("about about", "about"), ("grow though", "grow through"),
    ("media excision", "media execution"), ("Digtial", "Digital"),
    ("Entrainment", "Entertainment"), ("across the 5 of the main", "across 5 of the main"),
    ("test and learning", "test and learn"),
]
ROLE_FIXES = {
    "Senior Account Director at Kines": "Senior Account Director at Kinesso",
    "EMEA Media Associate Manager at Spot": "EMEA Media Associate Manager at Spotify",
    "Global Media Lead at Lumene G": "Global Media Lead at Lumene Group",
    "Director, Client Strategy at Publicis G": "Director, Client Strategy at Publicis Groupe",
    "Managing Partner at OM": "Managing Partner at OMD",
    "Managing Partner, Head of Business Transformation at O": "Managing Partner, Head of Business Transformation at OMD",
    "Senior Consultant at Me": "Senior Consultant",
    "Account Management Lead at": "Account Management Lead",
    "MD at": "Managing Director",
    "Global Client Vice Presiden": "Global Client Vice President",
    "Group Director, Paid Socia": "Group Director, Paid Social",
    "Head of": "Head of Marketing",
    "Lead Product De": "Lead Product Designer",
    "Director of Communications & Public Engagement at Oxford alth": "Director of Communications & Public Engagement at Oxford Health",
    "Lead at un-held  ex BBH": "Lead at un-held, ex BBH",
}

NAV = [("About", "/about/"), ("Tech & Media", "/Blog/TechMedia/"), ("Travel", "/Blog/Travel/"), ("Newsletter", "/Blog/Newsletters/")]
SPECIAL_URLS = {"Home": "/", "Gaming": "/gaming/", "List of Games to Play": "/gaming/games-to-play/", "PC Desk Setups": "/gaming/pc-setup/"}

EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍\U0001F1E6-\U0001F1FF\U000E0000-\U000E007F⬀-⯿]+")
missing_images = set()

# ---------------------------------------------------------------- helpers

def esc(s):
    return html.escape(s, quote=True)


def fix_text(s):
    for a, b in FIXES:
        s = s.replace(a, b)
    return s


def no_dash(s, title=False):
    """House style: no em dashes."""
    if title:
        s = re.sub(r"\s*—\s*", ": ", s, count=1)
    return re.sub(r"\s*—\s*", ", ", s)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def norm_url(permalink):
    p = permalink.strip().strip("/")
    return "/" if p in ("", "Home") else f"/{p}/"


def parse_date(s):
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", s or "")
    if not m:
        return None
    d, mth, y = (int(x) for x in m.groups())
    if y < 100:
        y += 2000
    try:
        return dt.date(y, mth, d)
    except ValueError:
        return None


def nice_date(d):
    return f"{d.day} {d.strftime('%B %Y')}" if d else ""


def strip_md(s):
    s = re.sub(r"!\[\[[^\]]*\]\]", "", s)
    s = re.sub(r"\[\[([^\]|]*\|)?([^\]]+)\]\]", r"\2", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    return re.sub(r"[*_`#>]", "", s).strip()


# ---------------------------------------------------------------- images

IMAGES = {}
for p in SRC.rglob("*"):
    if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp") and p.is_file():
        IMAGES.setdefault(p.name, p)
_done = {}


def image(name):
    """Resize a vault image to WebP. Returns (url, w, h) or None."""
    name = name.strip().rstrip("\\")
    if name in _done:
        return _done[name]
    src = IMAGES.get(Path(name).name)
    res = None
    if src:
        out = IMG_OUT / (slug(Path(name).stem) + ".webp")
        try:
            if out.exists() and out.stat().st_mtime >= src.stat().st_mtime:
                with Image.open(out) as im:
                    res = (f"/img/{out.name}", im.width, im.height)
            else:
                with Image.open(src) as im:
                    im = ImageOps.exif_transpose(im)
                    if im.mode not in ("RGB", "RGBA"):
                        im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
                    if im.width > MAX_W:
                        im = im.resize((MAX_W, round(im.height * MAX_W / im.width)), Image.LANCZOS)
                    IMG_OUT.mkdir(parents=True, exist_ok=True)
                    im.save(out, "WEBP", quality=80, method=5)
                    res = (f"/img/{out.name}", im.width, im.height)
        except OSError:
            res = None
    if res is None:
        missing_images.add(name)
    _done[name] = res
    return res


def img_tag(name, width=None, cls="", alt=""):
    r = image(name)
    if not r:
        return ""
    url, w, h = r
    style = f' style="width:{width}px"' if width else ""
    c = f' class="{cls}"' if cls else ""
    return f'<img src="{url}" width="{w}" height="{h}" alt="{esc(alt)}" loading="lazy" decoding="async"{c}{style}>'


# ---------------------------------------------------------------- notes

class Note:
    def __init__(self, path):
        self.path = path
        raw = path.read_text(encoding="utf-8")
        self.fm, body = {}, raw
        m = re.match(r"^---\n(.*?)\n---\n?", raw, re.S)
        if m:
            try:
                self.fm = yaml.safe_load(m.group(1)) or {}
            except yaml.YAMLError:
                self.fm = {}
            body = raw[m.end():]
        self.raw_body = body
        h1 = re.search(r"^# (.+)$", body, re.M)
        self.title = EMOJI.sub("", no_dash(fix_text(h1.group(1).strip()), title=True)).strip() if h1 else path.stem
        self.name = path.stem
        if self.name in SPECIAL_URLS:
            self.url = SPECIAL_URLS[self.name]
        elif self.fm.get("permalink"):
            self.url = norm_url(str(self.fm["permalink"]))
        else:
            self.url = "/" + slug(self.name) + "/"
        dm = re.search(r"Date Posted:\**\s*(.+)", body)
        self.date = parse_date(dm.group(1)) if dm else None
        if not self.date:
            fm_ = re.match(r"(\d{4})-(\d{2})-(\d{2})", self.name)
            if fm_:
                self.date = dt.date(*map(int, fm_.groups()))
        loc = re.search(r"^Location:\s*(.+)$", body, re.M)
        self.location = EMOJI.sub("", loc.group(1)).strip() if loc else ""
        vis = re.search(r"^Visited:\s*(.+)$", body, re.M)
        self.visited = vis.group(1).strip() if vis else ""
        emb = re.search(r"!\[\[([^\]|]+)", body)
        self.cover = emb.group(1) if emb else None
        rel = path.relative_to(SRC).as_posix()
        self.kind = ("travel" if rel.startswith("Blog/Travel Posts/") else
                     "tech" if rel.startswith("Blog/Tech & Media/") else
                     "newsletter" if rel.startswith("Blog/Newsletters/") else "page")

    def excerpt(self, n=160):
        for line in self.clean_body().splitlines():
            t = strip_md(re.sub(r"^\s*([-*+]|\d+\.)\s+", "", line))
            if len(t) > 40 and not line.startswith(("#", "|", "!")):
                t = no_dash(fix_text(t))
                return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"
        return ""

    def clean_body(self):
        out = []
        h1_done = False
        for line in self.raw_body.splitlines():
            s = line.strip()
            if not h1_done and s.startswith("# "):
                h1_done = True
                continue
            if (s == "By Ian Adams" or s.startswith("**Date Posted:**") or s.startswith("Date Posted:")
                    or re.match(r"^(Tags|Location|Visited):", s) or s.startswith("[X](https://x.com")
                    or s.startswith("© 20") or s.startswith("## Feel free to get in touch")
                    or re.match(r"^#+\s*Find more", s) or s.startswith("Tags: #")):
                continue
            out.append(line)
        text = "\n".join(out).strip()
        text = re.sub(r"^(?:-{3,}\s*\n\s*)+", "", text)
        text = re.sub(r"(?:\n\s*-{3,}\s*)+$", "", text)
        text = re.sub(r"(\n-{3,}\s*\n)(\s*\n?-{3,}\s*\n)+", r"\1", text)
        return text.strip()


NOTES = [Note(p) for p in sorted(SRC.rglob("*.md"))]
BY_NAME = {n.name: n for n in NOTES}


def resolve(target):
    base = target.split("#")[0].strip()
    return BY_NAME.get(Path(base).name)


# ---------------------------------------------------------------- markdown

MD = markdown.Markdown(extensions=["tables", "sane_lists", "nl2br", "fenced_code"])


def preprocess(text):
    # broken nested links: [Label]([text](url)) -> [Label](url)
    text = re.sub(r"\[([^\]]+)\]\(\[[^\]]*\]\((https?://[^)\s]+)\)\)", r"[\1](\2)", text)

    def embed(m):
        inner = m.group(1).replace("\\|", "|")
        target, _, size = inner.partition("|")
        if Path(target).suffix.lower() not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            return ""
        width = int(size) if size.strip().isdigit() else None
        return img_tag(target, width, "" if width else "full")
    text = re.sub(r"!\[\[([^\]]+)\]\]", embed, text)


    def link(m):
        inner = m.group(1).replace("\\|", "|")
        target, _, alias = inner.partition("|")
        label = alias or Path(target.split("#")[0]).name
        n = resolve(target)
        return f"[{label}]({n.url})" if n else label
    text = re.sub(r"\[\[([^\]]+)\]\]", link, text)
    def callout(m):
        title = (m.group(2) or m.group(1)).strip().capitalize()
        inner = "\n".join(re.sub(r"^>\s?", "", l) for l in m.group(3).splitlines())
        body = markdown.Markdown(extensions=["tables", "sane_lists"]).convert(inner)
        return f'\n<aside class="callout"><p class="label">{esc(title)}</p>{body}</aside>\n'
    text = re.sub(r"^> \[!(\w+)\][+-]? ?(.*)\n((?:>.*(?:\n|$))*)", callout, text, flags=re.M)

    lines, out = text.splitlines(), []
    for i, line in enumerate(lines):
        line = line.replace("\t", "    ")
        is_list = re.match(r"^\s*([-*+]|\d+\.)\s", line)
        is_table = line.lstrip().startswith("|")
        if out:
            prev = out[-1]
            prev_list = re.match(r"^\s*([-*+]|\d+\.)\s", prev)
            if is_list and prev.strip() and not prev_list:
                out.append("")
            elif is_table and prev.strip() and not prev.lstrip().startswith("|"):
                out.append("")
        out.append(line)
    text = "\n".join(out)
    text = text.replace("~~", "")
    text = re.sub(r"^(#{1,6})\s+#?(.*)$", lambda m: m.group(1) + " " + EMOJI.sub("", m.group(2)).strip(), text, flags=re.M)
    return no_dash(fix_text(text))


def render(text):
    MD.reset()
    html_ = MD.convert(preprocess(text))
    html_ = re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" rel="noopener" target="_blank"', html_)
    return html_


# ---------------------------------------------------------------- layout

def page(path_url, title, body, current=None, desc=None, label=None, dest=None):
    desc = desc or f"Ian Adams, {TITLE}. {STRAP}"
    full_title = "Ian Adams · " + TITLE if path_url == "/" else f"{title} · Ian Adams"
    cur = ' aria-current="page"'
    nav = "".join(
        f'<a href="{u}"{cur if current == u else ""}>{esc(t)}</a>' for t, u in NAV)
    doc = f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{SITE_URL}{path_url}">
<meta property="og:title" content="{esc(full_title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{SITE_URL}{path_url}">
<meta name="theme-color" content="#F7F9FA" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#121C23" media="(prefers-color-scheme: dark)">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/style.css?v={CSS_V}">
</head>
<body>
<header class="site-header"><div class="wrap">
<a class="mark" href="/" aria-label="Ian Adams, home">ian adams<span class="dot">.</span></a>
<nav class="nav" aria-label="Main">{nav}</nav>
</div></header>
<main>
{body}
</main>
<section class="contact" aria-labelledby="contact-h"><div class="wrap">
<p class="label">Get in touch</p>
<h2 id="contact-h">Let's talk media.</h2>
<p>Email <a href="mailto:{EMAIL}">{EMAIL}</a> or find me on <a href="https://www.linkedin.com/in/ianmartinadams/" rel="noopener">LinkedIn</a>.</p>
</div></section>
<footer class="site-footer"><div class="wrap">
<div>© {YEAR} Ian Adams · {esc(STRAP)} · Views are my own</div>
<nav aria-label="Footer"><a href="/Pins/">Pins</a><a href="/gaming/">Gaming</a><a href="/Links/">Links</a><a href="https://www.linkedin.com/in/ianmartinadams/" rel="noopener">LinkedIn</a><a href="https://www.instagram.com/ianadams3/" rel="noopener">Instagram</a><a href="https://x.com/ianmartinadams" rel="noopener">X</a></nav>
</div></footer>
</body>
</html>
"""
    if dest is None:
        dest = OUT / path_url.strip("/") / "index.html" if path_url != "/" else OUT / "index.html"
        PAGES.append(path_url)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(doc, encoding="utf-8")


import hashlib
CSS_V = hashlib.md5((ROOT / "assets" / "style.css").read_bytes()).hexdigest()[:8]
PAGES = []
EMAIL = "adamsian3@gmail.com"


def post_card(n, show_excerpt=True):
    ex = f'<p class="muted small" style="margin:0">{esc(n.excerpt())}</p>' if show_excerpt else ""
    return (f'<a class="card" href="{n.url}"><span class="meta">{esc(nice_date(n.date))}</span>'
            f'<h3>{esc(n.title)}</h3>{ex}</a>')


def travel_card(n):
    cover = img_tag(n.cover, alt=n.title) if n.cover else ""
    if not cover:
        cover = '<img alt="" src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" width="16" height="9">'
    where = "" if (n.location or "").strip() == n.title else (n.location or "")
    return (f'<a class="card photo" href="{n.url}">{cover}<div class="body">'
            f'<h3>{esc(n.title)}</h3><span class="meta">{esc(where)}</span></div></a>')


# ---------------------------------------------------------------- pages

def build_post(n, section_label, section_url):
    meta = []
    if n.date:
        meta.append(f"<span>{esc(nice_date(n.date))}</span>")
    if n.location:
        meta.append(f"<span>{esc(n.location)}</span>")
    if n.visited:
        meta.append(f"<span>Visited {esc(n.visited)}</span>")
    body = f"""<div class="wrap">
<header class="post-head prose">
<p class="label"><a href="{section_url}" style="color:inherit;text-decoration:none">{esc(section_label)}</a></p>
<h1>{esc(n.title)}</h1>
<div class="post-meta">{''.join(meta)}</div>
</header>
<article class="prose">{render(n.clean_body())}</article>
<a class="back" href="{section_url}">← All {esc(section_label)} posts</a>
</div>"""
    page(n.url, n.title, body, current=section_url, desc=n.excerpt() or None)


def build_home(home, about, tech, letters, travel):
    raw = home.raw_body
    lede_m = re.search(r"^### (.+)$", raw, re.M)
    lede = no_dash(fix_text(lede_m.group(1).strip())) if lede_m else ""
    years = re.search(r"(\d+)\s+years", raw)
    ab = about.raw_body
    agencies = re.search(r"(\d+)\s+agencies", ab)
    brands = re.search(r"(\d+)\s+brands", ab)
    platforms = re.search(r"(\d+\+?)\s+platforms", ab)
    stats = [(f"{years.group(1) if years else '12'}+", "years in digital media"),
             (agencies.group(1) if agencies else "7", "agencies across 5 networks"),
             (brands.group(1) if brands else "28", "brands supported"),
             (platforms.group(1) if platforms else "10+", "platforms planned and bought")]
    upd = re.search(r"### Recent updates\s*\n(.*?)\n---", raw, re.S)
    updates = render(re.sub(r"\)\s+\[", ") and [", upd.group(1).strip())) if upd else ""
    am = re.search(r"## About Me\s*\n(.*?)\n---", raw, re.S)
    bullets = []
    if am:
        for line in am.group(1).strip().splitlines():
            t = EMOJI.sub("", line).strip()
            if t:
                bullets.append("- " + t[0].upper() + t[1:])
    about_html = render("\n".join(bullets))
    latest = sorted([n for n in tech + letters if n.date], key=lambda n: n.date, reverse=True)[:3]
    trips = [n for n in travel if n.cover][:4]
    body = f"""<section class="hero" style="margin:0"><div class="wrap">
<p class="label">{esc(TITLE)}</p>
<h1 class="display">{esc(STRAP)}</h1>
<p class="lede">{esc(lede)}</p>
</div></section>
<div class="wrap">
<div class="stats">{''.join(f'<div class="stat"><b>{esc(a)}</b><span>{esc(b)}</span></div>' for a, b in stats)}</div>
<div class="two-col">
<section style="margin:0"><p class="label">Recent update</p><div class="prose">{updates}</div>
<p><a href="/about/">Roles, clients and testimonials →</a></p></section>
<section style="margin:0"><p class="label">About me</p><div class="prose">{about_html}</div></section>
</div>
<section><p class="label">Latest writing</p><h2 style="margin-top:0">Tech, media and monthly notes</h2>
<div class="grid">{''.join(post_card(n) for n in latest)}</div>
<p><a href="/Blog/TechMedia/">All Tech &amp; Media posts →</a></p></section>
<section><p class="label">Travel</p><h2 style="margin-top:0">Places I've been</h2>
<div class="grid">{''.join(travel_card(n) for n in trips)}</div>
<p><a href="/Blog/Travel/">The full travel blog →</a></p></section>
</div>"""
    page("/", "Home", body, desc=f"Ian Adams, {TITLE}. {lede}")


def table_rows(block):
    rows = []
    for line in block.splitlines():
        if not line.strip().startswith("|") or re.match(r"^\s*\|[\s:|-]+\|\s*$", line):
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
        rows.append(cells)
    return rows[1:] if rows else []


def build_about(about):
    raw = about.raw_body
    portrait = img_tag(about.cover, alt="Ian Adams", cls="portrait") if about.cover else ""
    head = re.search(r"^# (Ian Adams .+)$", raw, re.M)
    headline = no_dash(fix_text(head.group(1))) if head else ""
    seg = raw[head.end():] if head else raw
    seg = seg[:seg.find("**Clients")] if "**Clients" in seg else seg
    expert = re.findall(r"^- .+$", seg, re.M)
    expert_html = render("\n".join(expert))
    cm = re.search(r"\*\*Clients I.ve worked on:\*\*\s*(.+)", raw)
    clients = [c.strip() for c in cm.group(1).split(",")] if cm else []
    roles_block = re.search(r"## Roles\s*\n(.*?)\nOthers? Roles", raw, re.S)
    roles = table_rows(roles_block.group(1)) if roles_block else []
    roles_html = ""
    for r in roles:
        if len(r) < 4:
            continue
        when, role, org, cl = (fix_text(x) for x in r[:4])
        cl = re.sub(r"\s*<br>\s*", " · ", EMOJI.sub("", cl)).strip(" ·")
        cl = re.sub(r"\s+·", " ·", cl)
        when = when.replace(" - ", " to ").replace(" -", " to ")
        roles_html += (f'<li><div class="when">{esc(when)}</div><div><h3>{esc(role)}</h3>'
                       f'<p class="org">{esc(org.replace(" / ", " · "))}</p><p class="muted">{esc(cl)}</p></div></li>')
    other = re.search(r"Others? Roles:\s*\n(.*?)\n(?:##|\n)", raw, re.S)
    other_html = render(other.group(1)) if other else ""
    tm = re.search(r"## Testimonials\s*\n(.*?)(?:\n\s*\n\s*\n|\nTags:)", raw, re.S)
    quotes = ""
    for r in table_rows(tm.group(1) if tm else ""):
        if len(r) < 4:
            continue
        name = re.sub(r"<br>", "", r[1]).strip()
        role = ROLE_FIXES.get(r[2].strip(), r[2].strip())
        text = no_dash(fix_text(r[3]))
        paras = "".join(f"<p>{esc(p.strip())}</p>" for p in re.split(r"\s*<br>\s*<br>\s*", text) if p.strip())
        initials = "".join(w[0] for w in name.split()[:2]).upper()
        pic = re.search(r"!\[\[([^\]|\\]+)", r[0])
        avatar = img_tag(pic.group(1), cls="avatar", alt="") if pic else ""
        if not avatar:
            avatar = f'<span class="initials" aria-hidden="true">{esc(initials)}</span>'
        quotes += (f'<figure class="quote">{paras}<footer>{avatar}'
                   f'<div><cite>{esc(name)}</cite><div class="role">{esc(role)}</div></div></footer></figure>')
    body = f"""<div class="wrap">
<header class="page-head"><p class="label">About</p></header>
<div class="about-intro">
{portrait}
<div><h1>Ian Adams</h1><p style="color:var(--fjord);margin:0 0 16px">{esc(TITLE)}</p>
<p style="font-size:18px;line-height:28px;margin:0 0 16px">{esc(headline)}.</p>
<div class="prose">{expert_html}</div></div>
</div>
<section><p class="label">Clients</p><h2 style="margin-top:0">Brands I've worked on</h2>
<ul class="tags">{''.join(f'<li>{esc(c)}</li>' for c in clients)}</ul></section>
<section><p class="label">Experience</p><h2 style="margin-top:0">Roles</h2>
<ul class="roles">{roles_html}</ul>
<h3>Earlier roles</h3><div class="prose">{other_html}</div></section>
<section><p class="label">Testimonials</p><h2 style="margin-top:0">What people say</h2>
<div class="quotes">{quotes}</div></section>
</div>"""
    page("/about/", "About", body, current="/about/",
         desc=f"Ian Adams, {TITLE}. {headline}.")


def build_tech(index, tech):
    by_year = {}
    for n in sorted(tech, key=lambda n: n.date or dt.date.min, reverse=True):
        by_year.setdefault(n.date.year if n.date else "Undated", []).append(n)
    lists = ""
    for y, items in by_year.items():
        lis = "".join(f'<li><a href="{n.url}">{esc(n.title)}</a><span class="date">{esc(nice_date(n.date))}</span></li>' for n in items)
        lists += f'<h2 class="year">{y}</h2><ul class="list">{lis}</ul>'
    body = f"""<div class="wrap read">
<header class="page-head"><p class="label">Blog</p><h1>Tech &amp; Media</h1>
<p class="muted">Notes on platforms, launches and events I've been interested in, going back to 2011.</p></header>
{lists}
</div>"""
    page(index.url, "Tech & Media", body, current=index.url, desc="Ian Adams on tech, media and advertising platforms.")


def build_letters(index, letters):
    listed = {resolve(m).name for m in re.findall(r"\[\[([^\]|]+)", index.raw_body) if resolve(m)}
    items = sorted([n for n in letters if n.name in listed], key=lambda n: n.date or dt.date.min, reverse=True)
    body = f"""<div class="wrap">
<header class="page-head read"><p class="label">Blog</p><h1>Monthly newsletter</h1>
<p class="muted">A recap of each month: work, industry, tech and what I've been watching and playing.</p></header>
<section><div class="grid">{''.join(post_card(n) for n in items)}</div></section>
</div>"""
    page(index.url, "Newsletter", body, current=index.url, desc="Ian Adams' monthly newsletter.")
    return items


def build_travel(index, travel):
    raw = index.raw_body
    sections = re.split(r"^## ", raw, flags=re.M)[1:]
    out, seen = "", set()
    for sec in sections:
        lines = sec.splitlines()
        region = lines[0].strip()
        cards, soon = [], []
        body_lines = [l.replace("\t", "    ") for l in lines[1:]]
        for i, line in enumerate(body_lines):
            if not re.match(r"^\s*- ", line):
                continue
            item = line.split("- ", 1)[1].strip()
            m = re.search(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", item)
            if m:
                n = resolve(m.group(1))
                if n and n.url not in seen:
                    seen.add(n.url)
                    cards.append(travel_card(n))
                continue
            indent = len(line) - len(line.lstrip())
            nxt = body_lines[i + 1] if i + 1 < len(body_lines) else ""
            if re.match(r"^\s*- ", nxt) and len(nxt) - len(nxt.lstrip()) > indent:
                continue  # a country heading with places under it
            label = re.sub(r"\s*-?\s*\*?Coming soon\*?", "", item, flags=re.I).strip(" *-")
            if label and label.lower() != "none yet":
                soon.append(label)
        if cards or soon:
            grid = f'<div class="grid">{"".join(cards)}</div>' if cards else ""
            later = (f'<p class="soon-line"><span class="label" style="display:inline;margin-right:8px">Coming soon</span>'
                     f'{esc(" · ".join(soon))}</p>') if soon else ""
            out += f'<section><h2>{esc(region)}</h2>{grid}{later}</section>'
    body = f"""<div class="wrap">
<header class="page-head read"><p class="label">Blog</p><h1>Travel</h1>
<p class="muted">Notes and photos from the places I've been, with where to eat and what to see.</p></header>
{out}
</div>"""
    page(index.url, "Travel", body, current=index.url, desc="Ian Adams' travel blog: notes and photos from trips.")


def build_generic(n, label, current=None):
    body = f"""<div class="wrap">
<header class="post-head prose"><p class="label">{esc(label)}</p><h1>{esc(n.title if n.title != n.name or label != 'Gaming' else n.name)}</h1></header>
<article class="prose">{render(n.clean_body())}</article>
</div>"""
    page(n.url, n.title, body, current=current)


def build_links(n):
    text = preprocess(n.clean_body())
    groups, cur = {"Find me": []}, "Find me"
    for line in text.splitlines():
        s = line.strip().lstrip("-* ").strip()
        if not s:
            continue
        m = re.match(r"^\[([^\]]+)\]\(([^)\s]+)\)$", s)
        if m:
            label, url = m.groups()
            if url.rstrip("/") in ("https://ianadams.media", "https://www.ianadams.media"):
                continue
            url = re.sub(r"^https?://(www\.)?ianadams\.media", "", url)
            url = {"/Blog/Travel": "/Blog/Travel/", "/Blog/TechMedia": "/Blog/TechMedia/"}.get(url, url)
            groups[cur].append((label, url))
        elif not s.startswith("["):
            cur = {"Old": "Older profiles"}.get(s, s)
            groups.setdefault(cur, [])
    cols = ""
    for g, items in groups.items():
        if not items:
            continue
        rel = ' rel="noopener"'
        lis = "".join(
            f'<li><a href="{esc(u)}"{rel if u.startswith("http") else ""}>{esc(l)}</a></li>' for l, u in items)
        cols += f'<section style="margin:0"><p class="label">{esc(g)}</p><ul class="list">{lis}</ul></section>'
    body = f"""<div class="wrap">
<header class="page-head"><p class="label">Elsewhere</p><h1>Links</h1></header>
<div class="grid" style="margin-top:24px">{cols}</div>
</div>"""
    page(n.url, "Links", body)


PINS_JS = r"""
(() => {
  const pins = JSON.parse(document.getElementById('pins-data').textContent);
  const board = document.getElementById('board'), filters = document.getElementById('filters');
  const count = document.getElementById('pin-count'), dlg = document.getElementById('dlg');
  const search = document.getElementById('pin-search');
  let current = 'All', visible = pins, openIndex = -1;
  const norm = t => (t || '').toLowerCase();
  const hash = s => [...s].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7);
  const jitter = (id, salt, range) => ((hash(id + salt) % 1000) / 1000 * 2 - 1) * range;
  function badge(p) {
    const el = document.createElement('div');
    el.className = 'badge ' + (p.image ? 'photo' : (p.shape || 'circle'));
    el.style.setProperty('--bg', p.bg || '#ddd'); el.style.setProperty('--rim', p.rim || '#999'); el.style.setProperty('--fg', p.fg || '#222');
    if (p.image) { const img = document.createElement('img'); img.src = p.image; img.alt = p.name; el.append(img); }
    else {
      const txt = p.label || p.name, longest = Math.max(...txt.split(' ').map(w => w.length));
      if (longest > 7 || txt.length > 12) el.classList.add(longest > 9 ? 'xlong' : 'long');
      el.textContent = txt; el.setAttribute('aria-hidden', 'true');
    }
    return el;
  }
  ['All', ...new Set(pins.map(p => p.category))].forEach(c => {
    const b = document.createElement('button');
    b.className = 'chip'; b.type = 'button'; b.textContent = c;
    b.addEventListener('click', () => { current = c; render(); });
    filters.append(b);
  });
  function render() {
    const q = norm(search.value).trim();
    visible = pins.filter(p => (current === 'All' || p.category === current) &&
      (!q || [p.name, p.label, p.where, p.category, p.description, p.acquired].some(f => norm(f).includes(q))));
    filters.querySelectorAll('.chip').forEach(b => b.setAttribute('aria-pressed', String(b.textContent === current)));
    count.textContent = visible.length + (visible.length === 1 ? ' pin' : ' pins');
    board.replaceChildren();
    if (!visible.length) { const e = document.createElement('p'); e.className = 'pin-empty'; e.textContent = 'No pins match that search.'; board.append(e); return; }
    visible.forEach((p, i) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'pin'; b.setAttribute('aria-label', p.name + ', open details');
      b.style.setProperty('--r', jitter(p.id, 'r', 9).toFixed(1) + 'deg');
      b.style.setProperty('--dx', jitter(p.id, 'x', 8).toFixed(1) + 'px');
      b.style.setProperty('--dy', jitter(p.id, 'y', 8).toFixed(1) + 'px');
      b.title = p.name;
      b.append(badge(p)); b.addEventListener('click', () => open(i)); board.append(b);
    });
  }
  function row(id, val) { const dd = document.getElementById(id); dd.textContent = val || ''; dd.hidden = dd.previousElementSibling.hidden = !val; }
  function open(i) {
    openIndex = (i + visible.length) % visible.length;
    const p = visible[openIndex];
    document.getElementById('dlg-badge').replaceChildren(badge(p));
    document.getElementById('dlg-title').textContent = p.name;
    row('dlg-when', p.acquired); row('dlg-where', p.where); row('dlg-cat', p.category);
    const s = document.getElementById('dlg-story'); s.textContent = p.description || ''; s.hidden = !p.description;
    if (!dlg.open) dlg.showModal();
  }
  document.getElementById('close').addEventListener('click', () => dlg.close());
  document.getElementById('prev').addEventListener('click', () => open(openIndex - 1));
  document.getElementById('next').addEventListener('click', () => open(openIndex + 1));
  dlg.addEventListener('click', e => { if (e.target === dlg) dlg.close(); });
  dlg.addEventListener('keydown', e => { if (e.key === 'ArrowRight') open(openIndex + 1); if (e.key === 'ArrowLeft') open(openIndex - 1); });
  search.addEventListener('input', render);
  render();
})();
"""


def build_pins():
    src = ROOT / "pins" / "pins.json"
    if not src.exists():
        return
    pins = json.loads(src.read_text(encoding="utf-8"))
    for p in pins:
        if p.get("image") and not p["image"].startswith(("/", "http")):
            local = ROOT / "pins" / p["image"]
            if local.exists():
                dest = OUT / "img" / "pins" / local.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(local, dest)
                p["image"] = f"/img/pins/{local.name}?v={int(local.stat().st_mtime)}"
            else:
                r = image(Path(p["image"]).name)
                p["image"] = r[0] if r else None
        for k in ("name", "description", "where", "acquired", "label"):
            if isinstance(p.get(k), str):
                p[k] = no_dash(p[k])
    data = json.dumps(pins, ensure_ascii=False).replace("</", "<\\/")
    body = f"""<div class="wrap">
<header class="page-head pins-head">
<div><p class="label">Collection</p><h1>Pins</h1>
<p class="muted" style="max-width:60ch">Enamel pins collected over the years from trips, gigs, jobs and the odd football shop. Tap a pin to see where it came from.</p></div>
<p class="muted small" id="pin-count"></p>
</header>
<div class="pin-tools">
<label class="pin-search"><span class="label" style="margin:0">Search</span><input type="search" id="pin-search" placeholder="Try West Ham, Dublin or Sport" autocomplete="off"></label>
<div class="filters" id="filters" role="group" aria-label="Filter pins"></div>
</div>
<div class="cork-frame"><div class="board" id="board" aria-live="polite"></div></div>
</div>
<dialog id="dlg" aria-labelledby="dlg-title"><div class="pin-card">
<button class="close" id="close" aria-label="Close">×</button>
<div id="dlg-badge"></div>
<h2 id="dlg-title"></h2>
<dl class="meta"><dt>Got it</dt><dd id="dlg-when"></dd><dt>Where</dt><dd id="dlg-where"></dd><dt>Category</dt><dd id="dlg-cat"></dd></dl>
<p class="story" id="dlg-story"></p>
<div class="pin-nav"><button id="prev">← Previous</button><button id="next">Next →</button></div>
</div></dialog>
<script type="application/json" id="pins-data">{data}</script>
<script>{PINS_JS}</script>"""
    page("/Pins/", "Pins", body, desc="Ian Adams' enamel pin collection on a digital corkboard.")


def extras():
    shutil.copytree(ROOT / "assets", OUT / "assets", dirs_exist_ok=True)
    (OUT / "favicon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="#1F3442"/>'
        '<text x="9" y="44" font-family="Hanken Grotesk, Helvetica Neue, Arial, sans-serif" font-weight="600" '
        'font-size="34" letter-spacing="-1.5" fill="#F7F9FA">ia<tspan fill="#7FA9A1">.</tspan></text></svg>', encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    urls = "".join(f"<url><loc>{SITE_URL}{u}</loc></url>" for u in sorted(set(PAGES)))
    (OUT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n', encoding="utf-8")
    (OUT / "_redirects").write_text("/Home / 301\n/Home/ / 301\n/About /about/ 301\n/About/ /about/ 301\n", encoding="utf-8")


def build_gaming():
    """The /gaming/ page: a hand-built game-menu layout kept in gaming/body.html."""
    src = ROOT / "gaming" / "body.html"
    if not src.exists():
        return False
    page("/gaming/", "Gaming", src.read_text(encoding="utf-8"), current="/gaming/",
         desc="Ian Adams' gaming page: what I'm playing, my quest log, setup and all-time favourites.")
    return True


def build_404():
    body = """<div class="wrap read"><header class="page-head"><p class="label">404</p><h1>That page isn't here.</h1>
<p class="muted">It may have moved when the site was rebuilt. Try the <a href="/">home page</a>, <a href="/Blog/TechMedia/">Tech &amp; Media</a> or <a href="/Blog/Travel/">Travel</a>.</p></header></div>"""
    page("/404", "Not found", body, dest=OUT / "404.html")


def main():
    if not SRC.exists():
        sys.exit(f"Can't find the vault folder: {SRC}")
    for p in OUT.glob("*"):
        if p.name != "img":
            try:
                shutil.rmtree(p) if p.is_dir() else p.unlink()
            except OSError:
                pass  # stale files are simply overwritten
    OUT.mkdir(exist_ok=True)
    tech = [n for n in NOTES if n.kind == "tech"]
    letters_all = [n for n in NOTES if n.kind == "newsletter"]
    travel = sorted([n for n in NOTES if n.kind == "travel"], key=lambda n: n.date or dt.date.min, reverse=True)
    letters = build_letters(BY_NAME["Newsletters"], letters_all)
    build_home(BY_NAME["Home"], BY_NAME["About me"], tech, letters, travel)
    build_about(BY_NAME["About me"])
    build_tech(BY_NAME["Tech & Media"], tech)
    build_travel(BY_NAME["Travel Blog"], travel)
    for n in tech:
        build_post(n, "Tech & Media", "/Blog/TechMedia/")
    for n in travel:
        build_post(n, "Travel", "/Blog/Travel/")
    for n in letters:
        build_post(n, "Newsletter", "/Blog/Newsletters/")
    custom_gaming = build_gaming()
    for nm in ("Gaming", "List of Games to Play", "PC Desk Setups"):
        if nm == "Gaming" and custom_gaming:
            continue
        if nm in BY_NAME:
            build_generic(BY_NAME[nm], "Gaming")
    build_links(BY_NAME["Links"])
    build_pins()
    build_404()
    extras()
    print(f"Built {len(PAGES)} pages into {OUT}")
    if missing_images:
        print(f"{len(missing_images)} images couldn't be read (not downloaded from iCloud?) and were left out:")
        for m in sorted(missing_images)[:15]:
            print("  -", m)
        (ROOT / "missing-images.json").write_text(json.dumps(sorted(missing_images), indent=1))


if __name__ == "__main__":
    main()
