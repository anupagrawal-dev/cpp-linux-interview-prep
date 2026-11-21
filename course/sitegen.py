# -*- coding: utf-8 -*-
"""Static-site engine for the study course.

gen_study.py owns the content (topics + questions); this module turns it into ./site/.
No dependencies beyond the standard library. Output works from file:// (relative links,
no fetch(), no CDN).
"""
import os, re, html, json, shutil, hashlib, random

SITE_TITLE = "C++ / Linux Interview Prep"
COURSE_TITLE = "C++ / Linux Interview Prep — Revision Course"
COURSE_BLURB = ("My revision course for C++ and Linux systems interviews: C++11/14 core and modern C++, the STL, "
                "concurrency, Linux processes and threads, TCP and sockets, and security basics. Read a lesson, test yourself, "
                "then come back to what you got wrong.")

CAT_ORDER = ["C++ Core", "Modern C++", "STL", "Concurrency", "Linux", "Networking", "Security"]
CAT_BLURB = {
    "C++ Core": "Types, const, arrays, pointers and references, memory, classes, object lifetime, inheritance and virtual functions.",
    "Modern C++": "Value categories and move, smart pointers, exceptions and RAII, lambdas, templates, casts and constexpr.",
    "STL": "Containers, iterators and algorithms: what each one costs and when to use it.",
    "Concurrency": "std::thread, mutexes, condition variables, atomics, futures and the classic thread problems.",
    "Linux": "Processes, fork/exec/wait, pipes, signals, pthreads and semaphores, from a systems angle.",
    "Networking": "How TCP works and how to write clients and servers with sockets.",
    "Security": "Memory corruption, exploits and mitigations, hashing, public-key cryptography and TLS.",
}
# standalone deep-dive pages (source in ./extras, published to site/extras) and the lessons that point at them
EXTRAS = {}
# question types (see Q() in gen_study.py); option keys are A, B, C ...
CHOICE_TYPES = ("mcq", "multi", "tf")
QTYPES = ("short", "output") + CHOICE_TYPES
TYPE_LABEL = {"mcq": "Multiple choice", "multi": "Multiple answers", "tf": "True / False", "output": "Predict the output", "short": "Written"}
KEYS = "ABCDEFGH"
PRACTICE_MAX = 20          # weak-spot practice shows at most this many questions per round
def options_of(item): return ["True", "False"] if item.get("type") == "tf" else item.get("options", [])
def correct_indices(item):
    c = item.get("correct")
    if item.get("type") == "tf": return [0 if c else 1]
    return list(c) if isinstance(c, (list, tuple)) else [c]

MODULE_ICON = {"C++ Core": "{ }", "Modern C++": "&&", "STL": "[ ]", "Concurrency": "||", "Linux": "$_", "Networking": "<>", "Security": "!"}
WATCH_HEADING = re.compile(r"gotcha|pitfall|mistake|trap|caveat|careful|danger", re.I)

# ---------------------------------------------------------------- text helpers
def esc(t): return html.escape(t, quote=False)
def attr(t): return html.escape(t, quote=True)

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITAL = re.compile(r"(?<![*\w])\*(?![\s*])(.+?)(?<![\s*])\*(?![*\w])")
def inline(t):
    """Escape, then **bold**, *italic*, `code`. Code spans are protected so C++ like `int* p` survives."""
    spans = []
    def stash(m):
        spans.append("<code>%s</code>" % esc(m.group(1))); return "\x00%d\x00" % (len(spans) - 1)
    s = esc(re.sub(r"`([^`]+)`", stash, t))          # code spans become placeholders so **bold** may wrap them
    s = _BOLD.sub(r"<strong>\1</strong>", s)
    s = _ITAL.sub(r"<em>\1</em>", s)
    return re.sub("\x00(\\d+)\x00", lambda m: spans[int(m.group(1))], s)

LANG_LABEL = {"cpp": "C++", "c": "C", "bash": "Bash", "sh": "Shell", "python": "Python", "output": "Output", "text": "Example output", "": "Code"}

# build-time syntax highlighting (no JS, no CDN): one regex pass, longest/most specific alternatives first
_CPP_KW = ("alignas alignof auto bool break case catch char char16_t char32_t char8_t class const consteval constexpr constinit "
           "const_cast continue decltype default delete do double dynamic_cast else enum explicit export extern false final float "
           "for friend goto if inline int long mutable namespace new noexcept nullptr operator override private protected public "
           "register reinterpret_cast return short signed sizeof static static_assert static_cast struct switch template this "
           "thread_local throw true try typedef typeid typename union unsigned using virtual void volatile while size_t uint8_t "
           "uint16_t uint32_t uint64_t int8_t int16_t int32_t int64_t uintptr_t").split()
_CPP = re.compile(
    r"(?P<com>//[^\n]*|/\*.*?\*/)"
    r"|(?P<pre>^[ \t]*#[ \t]*\w+[^\n]*)"
    r"|(?P<str>\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])+')"
    r"|(?P<num>\b(?:0[xX][0-9a-fA-F']+|0[bB][01']+|\d[\d']*\.?\d*(?:[eE][+-]?\d+)?)[uUlLfF]*\b)"
    r"|(?P<kw>\b(?:%s)\b)"
    r"|(?P<std>\bstd::\w+)"
    r"|(?P<fn>\b[A-Za-z_]\w*(?=\s*\())" % "|".join(_CPP_KW), re.S | re.M)
_SH = re.compile(
    r"(?P<com>(?:^|(?<=\s))#[^\n]*)"
    r"|(?P<str>\"(?:\\.|[^\"\\])*\"|'[^']*')"
    r"|(?P<pre>^\s*\$(?=\s))"
    r"|(?P<kw>\b(?:if|then|else|fi|for|do|done|while|case|esac|in|function|export|sudo)\b)"
    r"|(?P<fn>(?:(?<=^)|(?<=\$ )|(?<=\| )|(?<=&& ))[A-Za-z_][\w.-]*)", re.M)
_HL = {"cpp": _CPP, "c": _CPP, "bash": _SH, "sh": _SH}

def highlight(code, lang):
    rx = _HL.get(lang)
    if rx is None: return esc(code)
    out = []; pos = 0
    for m in rx.finditer(code):
        if m.start() == m.end(): continue
        out.append(esc(code[pos:m.start()]))
        out.append('<span class="tk-%s">%s</span>' % (m.lastgroup, esc(m.group(0))))
        pos = m.end()
    out.append(esc(code[pos:]))
    return "".join(out)

def code_block(code, lang=""):
    label = LANG_LABEL.get(lang, lang.upper() or "Code")
    return ('<figure class="code%s"><figcaption><span class="dots" aria-hidden="true"><i></i><i></i><i></i></span><span class="lang">%s</span>'
            '<button type="button" class="copy" aria-label="Copy code">Copy</button></figcaption>'
            '<pre><code>%s</code></pre></figure>') % (" code-output" if lang in ("output", "text") else "", label, highlight(code, lang))

def table_cells(row):
    """Split one '| a | b |' table row into cells. A '|' inside a `code span` (e.g. `a || b`) or written as '\\|' is kept."""
    cells, cur, in_code, i = [], "", False, 0
    s = row.strip()
    s = s[1:] if s.startswith("|") else s
    s = s[:-1] if s.endswith("|") and not s.endswith("\\|") else s
    while i < len(s):
        c = s[i]
        if c == "\\" and s[i + 1:i + 2] == "|": cur += "|"; i += 2; continue
        if c == "`": in_code = not in_code
        if c == "|" and not in_code: cells.append(cur.strip()); cur = ""
        else: cur += c
        i += 1
    cells.append(cur.strip())
    return cells

_TABLE_RULE = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$")

def md_table(rows):
    """Markdown pipe table -> HTML: the first row is the header, a '|---|---|' rule under it is skipped."""
    body = [r for r in rows if not _TABLE_RULE.match(r.strip())]
    head, rest = table_cells(body[0]), [table_cells(r) for r in body[1:]]
    th = "".join("<th scope=\"col\">%s</th>" % inline(c) for c in head)
    trs = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c) for c in r) for r in rest)
    return '<div class="table-wrap"><table class="md-table"><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (th, trs)

def md2html(text):
    if not text: return ""
    lines = text.split("\n"); out = []; i = 0
    while i < len(lines):
        ln = lines[i]; st = ln.strip()
        if st.startswith("```"):
            lang = st[3:].strip().lower(); code = []; i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i]); i += 1
            i += 1; out.append(code_block("\n".join(code), lang)); continue
        if st.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i]); i += 1
            out.append(md_table(rows)); continue
        if st.startswith("- "):
            items = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                items.append("<li>%s</li>" % inline(lines[i].strip()[2:])); i += 1
            out.append("<ul>%s</ul>" % "".join(items)); continue
        if re.match(r"\d+\.\s", st):
            items = []
            while i < len(lines) and re.match(r"\d+\.\s", lines[i].strip()):
                items.append("<li>%s</li>" % inline(re.sub(r"^\d+\.\s", "", lines[i].strip()))); i += 1
            out.append("<ol>%s</ol>" % "".join(items)); continue
        if st == "": i += 1; continue
        para = [ln]; i += 1
        while i < len(lines) and lines[i].strip() != "" and not lines[i].strip().startswith(("- ", "```", "|")) \
                and not re.match(r"\d+\.\s", lines[i].strip()):
            para.append(lines[i]); i += 1
        out.append("<p>%s</p>" % inline(" ".join(para)))
    return "\n".join(out)

def plain(t):
    """Markdown -> plain text for search and the progress list: drop ** / * emphasis and backticks, but keep a `*`
    that is C++ (in `*p` or `int* p` the star is inside backticks, so code spans are unwrapped, not stripped)."""
    spans = []
    t = re.sub(r"`([^`]+)`", lambda m: spans.append(m.group(1)) or "\x00%d\x00" % (len(spans) - 1), t)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = _ITAL.sub(r"\1", t)
    return re.sub("\x00(\\d+)\x00", lambda m: spans[int(m.group(1))], t)

def slugify(t): return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-") or "section"
def fn(t): return "%02d-%s" % (t["order"], t["slug"])
def cat_slug(c): return "module-" + slugify(c)
def order_ranges(orders):
    """[1,2,3,32,33] -> '01–03, 32–33' (a module can span non-consecutive lessons)."""
    out = []; start = prev = None
    for o in sorted(orders) + [None]:
        if start is None: start = prev = o; continue
        if o is not None and o == prev + 1: prev = o; continue
        out.append("%02d" % start if start == prev else "%02d\u2013%02d" % (start, prev)); start = prev = o
    return ", ".join(out)
def show_note(item):
    n = item.get("note")
    return n if (n and n.strip().startswith("```")) else None

# ---------------------------------------------------------------- page shell
THEME_BOOT = ("(function(){var d=document.documentElement;try{var t=localStorage.getItem('prep.theme');"
              "d.setAttribute('data-theme',t==='light'?'light':'dark');}catch(e){d.setAttribute('data-theme','dark');}})();")

class Site:
    def __init__(self, topics):
        self.T = sorted(topics, key=lambda x: x["order"])
        self.N = len(self.T)
        self.by_slug = {t["slug"]: t for t in self.T}
        self.cats = [c for c in CAT_ORDER if any(t["cat"] == c for t in self.T)]
        extra_cats = sorted({t["cat"] for t in self.T} - set(CAT_ORDER))
        self.cats += extra_cats
        # global question numbering + stable ids (used by search, anchors, exam, future progress tracking)
        n = 0
        for t in self.T:
            for k, q in enumerate(t.get("quiz", [])):
                n += 1; q["n"] = n; q.setdefault("id", "%s-%02d" % (t["slug"], k + 1)); q["topic"] = t["slug"]
        self.total_q = n
        self.ver = "dev"   # asset version for cache-busting; set by build() from the asset contents
        self.mocks = []; self.mock_picks = {}     # set by build()

    def qcount(self, t): return len(t.get("quiz", []))

    def runs(self):
        """Question topics in learning order, grouped into consecutive same-category runs:
        [(category, label, [topics])]. Numbering follows learning order so saved exam answers stay valid."""
        out = []; seen = set()
        for t in self.T:
            if not t.get("quiz"): continue
            if out and out[-1][0] == t["cat"]: out[-1][2].append(t)
            else:
                out.append([t["cat"], t["cat"] + (" (continued)" if t["cat"] in seen else ""), [t]]); seen.add(t["cat"])
        return out

    # --- shared chrome
    def sidebar(self, root, active=None):
        cur = self.by_slug.get(active) if active else None
        parts = ['<nav class="sidebar" id="sidebar" aria-label="Course navigation">',
                 '<a class="sb-home%s" href="%sindex.html">Course home</a>' % (" is-current" if active == "home" else "", root)]
        for c in self.cats:
            items = [t for t in self.T if t["cat"] == c]
            opened = " open" if (cur is None or cur["cat"] == c) else ""
            parts.append('<details class="sb-group"%s><summary><span>%s</span><span class="sb-count" data-cat-slugs="%s">0/%d</span></summary><ul>'
                         % (opened, esc(c), " ".join(t["slug"] for t in items), len(items)))
            for t in items:
                cls = "sb-link" + (" is-current" if cur is t else "")
                parts.append('<li><a class="%s" data-slug="%s" href="%shtml/%s.html"%s><span class="sb-num">%02d</span>'
                             '<span class="sb-title-text">%s</span><span class="sb-check" aria-hidden="true"></span></a></li>'
                             % (cls, t["slug"], root, fn(t), ' aria-current="page"' if cur is t else "", t["order"], esc(t["title"])))
            parts.append("</ul></details>")
        parts.append('<div class="sb-section"><div class="sb-label">Practice</div>'
                     '<a class="sb-plain%s" href="%squestions/master-question-sheet.html">Question bank <span class="sb-badge">%d</span></a>'
                     '<a class="sb-plain%s" href="%squestions/exam-sheet.html">Exam sheet</a>'
                     '<a class="sb-plain%s" href="%squestions/progress.html">Progress</a>'
                     '<a class="sb-plain%s" href="%squestions/practice.html">Practice weak spots</a>'
                     '<a class="sb-plain%s" href="%squestions/mocks.html">Mock exams <span class="sb-badge">%d</span></a></div>'
                     % (" is-current" if active == "qbank" else "", root, self.total_q, " is-current" if active == "exam" else "", root,
                        " is-current" if active == "progress" else "", root, " is-current" if active == "practice" else "", root,
                        " is-current" if active == "mocks" else "", root, len(self.mocks)))
        parts.append('<div class="sb-section"><div class="sb-label">Deep dives</div>')
        for k, e in EXTRAS.items():
            parts.append('<a class="sb-plain" href="%sextras/%s">%s</a>' % (root, e["file"], esc(e["title"])))
        parts.append("</div></nav>")
        return "\n".join(parts)

    def shell(self, title, body, root, active=None, kind="page", extra_scripts="", desc=""):
        topbar = (
            '<header class="topbar">'
            '<button type="button" class="iconbtn menu-btn" id="menu-btn" aria-label="Open course menu" aria-controls="sidebar" aria-expanded="false">'
            '<span aria-hidden="true">&#9776;</span></button>'
            '<a class="brand" href="%sindex.html"><span class="brand-mark" aria-hidden="true">C++</span>'
            '<span class="brand-text">Systems Course<small>C/C++ &middot; Linux &middot; Memory</small></span></a>'
            '<span class="spacer"></span>'
            '<button type="button" class="searchbtn" id="open-search" aria-label="Search the course"><span aria-hidden="true">&#128269;</span>'
            '<span class="searchbtn-text">Search topics, concepts, questions&hellip;</span><kbd>/</kbd></button>'
            '<div class="theme-switch" role="group" aria-label="Colour theme">'
            '<button type="button" data-theme-set="dark" aria-pressed="true"><span aria-hidden="true">&#127769;</span><span class="ts-label"> Dark</span></button>'
            '<button type="button" data-theme-set="light" aria-pressed="false"><span aria-hidden="true">&#9728;</span><span class="ts-label"> Light</span></button>'
            '</div><div class="readbar" aria-hidden="true"><span id="readbar"></span></div></header>') % root
        return ('<!DOCTYPE html>\n<html lang="en" data-root="%s" data-theme="dark"><head><meta charset="UTF-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
                '<meta name="color-scheme" content="dark light">%s'
                '<title>%s</title><script>%s</script>'
                '<link rel="stylesheet" href="%sassets/style.css?v=%s"></head>'
                '<body class="%s"><a class="skip" href="#main">Skip to content</a>%s'
                '<div class="layout">%s<div class="scrim" id="scrim" hidden></div>'
                '<main id="main" tabindex="-1">%s</main></div>'
                '<script src="%sassets/search-index.js?v=%s"></script><script src="%sassets/app.js?v=%s" defer></script>%s</body></html>'
                ) % (root, ('<meta name="description" content="%s">' % attr(desc)) if desc else "", esc(title), THEME_BOOT,
                     root, self.ver, kind, topbar, self.sidebar(root, active), body, root, self.ver, root, self.ver, extra_scripts)

    # --- lesson page
    def lesson(self, i):
        t = self.T[i]; prev = self.T[i - 1] if i > 0 else None; nxt = self.T[i + 1] if i < self.N - 1 else None
        root = "../"
        pager_prev = ('<a href="%s.html" rel="prev"><span class="pg-dir">&larr; Previous</span><span class="pg-title">%02d. %s</span></a>' % (fn(prev), prev["order"], esc(prev["title"]))
                      if prev else '<a href="../index.html" rel="prev"><span class="pg-dir">&larr; Back</span><span class="pg-title">Course home</span></a>')
        pager_next = ('<a href="%s.html" rel="next" class="pg-next"><span class="pg-dir">Next &rarr;</span><span class="pg-title">%02d. %s</span></a>' % (fn(nxt), nxt["order"], esc(nxt["title"]))
                      if nxt else '<a href="../questions/master-question-sheet.html" rel="next" class="pg-next"><span class="pg-dir">Finished &rarr;</span><span class="pg-title">Question bank</span></a>')
        nq = self.qcount(t)
        details = t.get("detail", [])
        rel = [(k, e) for k, e in EXTRAS.items() if t["slug"] in e["lessons"]]
        mark_btn = ('<button type="button" class="btn btn-ghost mark-done" aria-pressed="false">'
                    '<span class="md-box" aria-hidden="true"></span><span class="md-text">Mark complete</span></button>')
        # "on this page" entries: (anchor, label, kind) — kind drives the dot colour in the side TOC
        toc = [("kp", "Key concepts", "concept")]
        toc += [(slugify(h), h, "watch" if WATCH_HEADING.search(h) else "plain") for h, _ in details]
        if rel: toc.append(("deeper", "Go deeper", "concept"))
        if t.get("confuse"): toc.append(("confused", "Easily confused", "watch"))
        toc.append(("test", "Test yourself", "plain"))
        p = []
        p.append('<div class="lesson-wrap"><article class="page lesson" data-slug="%s" data-order="%d">' % (t["slug"], t["order"]))
        p.append('<nav class="crumbs" aria-label="Breadcrumb"><a href="../index.html">Course</a><span aria-hidden="true">&rsaquo;</span>'
                 '<a href="../index.html#%s">%s</a><span aria-hidden="true">&rsaquo;</span><span aria-current="page">%s</span></nav>'
                 % (cat_slug(t["cat"]), esc(t["cat"]), esc(t["title"])))
        p.append('<header class="lesson-head"><div class="eyebrow"><span class="cat-tag">%s</span>'
                 '<span class="meta-item">Lesson %02d of %d</span><span class="meta-item">%d min read</span><span class="meta-item">%d question%s</span></div>'
                 '<h1>%s</h1><p class="lead">%s</p>'
                 '<div class="lesson-actions">%s<a class="btn btn-ghost" href="#test">Test yourself &darr;</a></div></header>'
                 % (esc(t["cat"]), t["order"], self.N, self.read_minutes(t), nq, "" if nq == 1 else "s",
                    esc(t["title"]), esc(t["summary"]), mark_btn))
        p.append('<p class="legend-inline"><span class="chip chip-concept"><span aria-hidden="true">&#9670;</span> Concept</span> core idea'
                 '<span class="chip chip-watch"><span aria-hidden="true">&#9650;</span> Watch out</span> easy to get wrong</p>')
        kp = "".join("<li>%s</li>" % inline(x) for x in t["points"])
        p.append('<section class="callout concept keypoints" aria-labelledby="kp"><div class="callout-label"><span aria-hidden="true">&#9670;</span> Concept</div>'
                 '<h2 id="kp">Key concepts</h2><ol class="kp-list">%s</ol></section>' % kp)
        if len(toc) > 2:
            p.append('<nav class="toc" aria-label="On this page (compact)"><span class="toc-label">On this page</span>%s</nav>'
                     % "".join('<a href="#%s">%s</a>' % (a, esc(l)) for a, l, _ in toc[1:]))
        for h, body in details:
            sid = slugify(h)
            if WATCH_HEADING.search(h):
                p.append('<section class="callout watch" aria-labelledby="%s"><div class="callout-label"><span aria-hidden="true">&#9650;</span> Watch out</div>'
                         '<h2 id="%s">%s</h2>%s</section>' % (sid, sid, esc(h), md2html(body)))
            else:
                p.append('<section class="section" aria-labelledby="%s"><h2 id="%s">%s</h2>%s</section>' % (sid, sid, esc(h), md2html(body)))
        if rel:
            rows = "".join('<a class="extra-link" href="../extras/%s"><strong>%s</strong><span>%s</span></a>' % (e["file"], esc(e["title"]), esc(e["blurb"])) for k, e in rel)
            p.append('<section class="callout concept" aria-labelledby="deeper"><div class="callout-label"><span aria-hidden="true">&#9670;</span> Deep dive</div>'
                     '<h2 id="deeper">Go deeper</h2><div class="extra-links">%s</div></section>' % rows)
        if t.get("confuse"):
            rows = "".join('<div class="pair"><div class="vs">%s</div><div class="d">%s</div></div>' % (inline(a), inline(d)) for a, d in t["confuse"])
            p.append('<section class="callout watch" aria-labelledby="confused"><div class="callout-label"><span aria-hidden="true">&#9650;</span> Watch out</div>'
                     '<h2 id="confused">Easily confused</h2><div class="pairs">%s</div></section>' % rows)
        p.append('<section class="test-card" id="test" aria-labelledby="test-h"><div class="test-icon" aria-hidden="true">?</div><div class="test-body">'
                 '<h2 id="test-h">Test yourself</h2>'
                 '<p>%d question%s on this lesson. Write your answers from memory, then compare them with the model answers side by side.</p>'
                 '<div class="test-actions"><a class="btn btn-primary" href="../questions/master-question-sheet.html#%s">Start the %d question%s &rarr;</a>%s</div></div></section>'
                 % (nq, "" if nq == 1 else "s", t["slug"], nq, "" if nq == 1 else "s", mark_btn))
        p.append('<div class="pager pager-bottom" aria-label="Lesson navigation">%s%s</div>' % (pager_prev, pager_next))
        p.append("</article>")
        p.append('<aside class="otp" aria-label="On this page"><div class="otp-inner"><div class="otp-label">On this page</div><ol>%s</ol>'
                 '<div class="otp-progress"><div class="otp-label">Module progress</div><div class="bar"><span id="otp-bar"></span></div>'
                 '<span class="otp-progress-text" id="otp-text" data-cat-slugs="%s"></span></div></div></aside></div>'
                 % ("".join('<li><a class="otp-%s" href="#%s">%s</a></li>' % (k, a, esc(l)) for a, l, k in toc),
                    " ".join(x["slug"] for x in self.T if x["cat"] == t["cat"])))
        return self.shell("%02d %s — %s" % (t["order"], t["title"], SITE_TITLE), "\n".join(p), root, active=t["slug"], kind="lesson", desc=t["summary"])

    def read_minutes(self, t):
        words = " ".join([t["summary"]] + t["points"] + [b for _, b in t.get("detail", [])] + ["%s %s" % c for c in t.get("confuse", [])]).split()
        return max(1, round(len(words) / 200))

    # --- course home
    def home(self):
        root = ""
        first = self.T[0]
        p = ['<div class="page home">']
        p.append('<header class="hero"><div class="hero-main"><div class="eyebrow"><span class="cat-tag">Engineering study course</span></div>'
                 '<h1>%s</h1><p class="lead">%s</p>'
                 '<div class="hero-actions"><a class="btn btn-primary btn-lg" id="continue" href="html/%s.html" data-default-label="Start course &rarr;" data-default-href="html/%s.html">Start course &rarr;</a>'
                 '<a class="btn btn-ghost btn-lg" href="questions/master-question-sheet.html">Question bank</a>'
                 '<a class="btn btn-ghost btn-lg" href="questions/exam-sheet.html">Exam sheet</a>'
                 '<a class="btn btn-ghost btn-lg" href="questions/mocks.html">Mock exams</a>'
                 '<a class="btn btn-ghost btn-lg" href="questions/progress.html">Progress</a></div></div>'
                 '<div class="hero-card" aria-label="Your progress"><div class="ring" id="ring" style="--p:0"><div class="ring-in"><b id="ring-pct">0%%</b><span>complete</span></div></div>'
                 '<div class="hero-card-text"><b id="overall-text">Not started yet</b><span id="overall-sub">Mark lessons complete to track progress here.</span></div>'
                 '<div class="overall" id="overall" data-total="%d" hidden><div class="bar"><span id="overall-bar"></span></div></div></div>'
                 '</header>' % (esc(SITE_TITLE), esc(COURSE_BLURB), fn(first), fn(first), self.N))
        p.append('<section class="stats" aria-label="Course at a glance">'
                 '<div><b>%d</b><span>Lessons</span></div><div><b>%d</b><span>Questions</span></div>'
                 '<div><b>%d</b><span>Modules</span></div><div><b>%d</b><span>Deep dives</span></div></section>'
                 % (self.N, self.total_q, len(self.cats), len(EXTRAS)))
        p.append('<h2 class="section-title">How it works</h2>'
                 '<ol class="flow" aria-label="How the course works">'
                 '<li><b>Learn</b><span>Read a lesson: key concepts first, then the details.</span></li>'
                 '<li><b>Practice</b><span>Write answers to its questions, then compare with the model answers.</span></li>'
                 '<li><b>Test</b><span>Take a timed mock exam, or write full answers in the exam sheet.</span></li>'
                 '<li><b>Review</b><span>Come back to what you missed.</span></li></ol>')
        p.append('<section class="legend" aria-label="Colour legend"><h2 class="sr-only">How to read the lessons</h2>'
                 '<div class="legend-item concept"><span class="chip chip-concept"><span aria-hidden="true">&#9670;</span> Concept</span>'
                 '<p>Blue: the core idea &mdash; definitions, how it works, key points, worked examples.</p></div>'
                 '<div class="legend-item watch"><span class="chip chip-watch"><span aria-hidden="true">&#9650;</span> Watch out</span>'
                 '<p>Amber: easily-confused pairs, gotchas and mistakes that cost marks or cause bugs.</p></div></section>')
        p.append('<h2 class="section-title">Modules</h2><div class="modules">')
        for mi, c in enumerate(self.cats):
            items = [t for t in self.T if t["cat"] == c]
            nq = sum(self.qcount(t) for t in items)
            p.append('<section class="module m%d" id="%s" data-slugs="%s" data-hrefs="%s" data-titles="%s">'
                     '<div class="module-top"><span class="module-icon" aria-hidden="true">%s</span><div><h3>%s</h3>'
                     '<span class="module-range">Lessons %s</span></div></div>'
                     '<p>%s</p><div class="module-meta"><span>%d lessons</span><span>%d questions</span></div>'
                     '<div class="module-prog"><div class="bar"><span></span></div><div class="module-progress-text">0 of %d complete</div></div>'
                     '<a class="btn btn-ghost module-go" href="html/%s.html" data-default-href="html/%s.html">Start &rarr;</a>'
                     '<details class="module-list"><summary>Lessons in this module</summary><ol>%s</ol></details></section>'
                     % (mi % 4, cat_slug(c), " ".join(t["slug"] for t in items), " ".join("html/%s.html" % fn(t) for t in items),
                        "|".join(esc(t["title"]) for t in items), MODULE_ICON.get(c, "&#9670;"), esc(c), order_ranges([t["order"] for t in items]),
                        esc(CAT_BLURB.get(c, "")), len(items), nq, len(items), fn(items[0]), fn(items[0]),
                        "".join('<li><a data-slug="%s" href="html/%s.html"><span class="ml-num">%02d</span> %s</a></li>' % (t["slug"], fn(t), t["order"], esc(t["title"])) for t in items)))
        p.append("</div>")
        p.append('<h2 class="section-title">Deep dives</h2><div class="extras">%s</div>'
                 % "".join('<a class="extra-link" href="extras/%s"><strong>%s</strong><span>%s</span></a>' % (e["file"], esc(e["title"]), esc(e["blurb"])) for e in EXTRAS.values()))
        p.append('<p class="foot-note">Progress and typed answers are stored only in this browser (localStorage). Nothing is sent anywhere. '
                 'Shortcuts: <kbd>/</kbd> search &middot; <kbd>&larr;</kbd> <kbd>&rarr;</kbd> previous / next lesson &middot; <kbd>Esc</kbd> close.</p>')
        p.append("</div>")
        return self.shell(COURSE_TITLE, "\n".join(p), root, active="home", kind="home", desc=COURSE_BLURB)

    # --- question cards
    def qcard(self, item, t, mode="bank", label=None):
        """One question: text, optional code snippet, then an input that depends on its type:
        short (default) -> free text; output -> exact program output; mcq / multi / tf -> options.
        The answer always lives in the textarea.ansinput (hidden for option types), so autosave, download and
        load work the same for every type. The model answer is in the page but hidden; compare.js shows it,
        auto-scores mcq / multi / tf / output, and asks for a self-mark otherwise."""
        n = item["n"]; qt = item.get("type", "short")
        data = ' data-type="%s"' % qt
        if qt in CHOICE_TYPES: data += ' data-correct="%s"' % ",".join(KEYS[i] for i in correct_indices(item))
        if qt == "output": data += ' data-expected="%s"' % attr(item["expected"])
        s = ['<article class="qcard" id="q%d" data-topic="%s" data-qid="%s"%s>' % (n, t["slug"], attr(item["id"]), data),
             '<header class="qmeta"><span class="qnum">%s</span>%s'
             '<a class="qtopic-link" href="../html/%s.html">%02d %s</a></header>'
             % (label or "Question %d" % n, ('<span class="qtype">%s</span>' % TYPE_LABEL[qt]) if qt != "short" else "", fn(t), t["order"], esc(t["title"])),
             '<div class="qtext">%s</div>' % inline(item["q"])]
        note = show_note(item)
        if note: s.append('<div class="qnote">%s</div>' % md2html(note))
        if item.get("explain"):
            s.append('<details class="expbox"><summary>What is this question asking?</summary><div class="exp">%s</div></details>' % md2html(item["explain"]))
        box_attrs = 'id="a%d" data-n="%d" data-id="%s" data-topic="%s" data-q="%s"' % (n, n, attr(item["id"]), attr("%02d %s" % (t["order"], t["title"])), attr(item["q"]))
        if qt in CHOICE_TYPES:
            kind = "checkbox" if qt == "multi" else "radio"
            hint = "Select all that apply" if qt == "multi" else "Choose one"
            opts = "".join('<label class="opt" data-key="%s"><input type="%s" name="o%d" value="%s"><span class="opt-key">%s</span><span class="opt-text">%s</span></label>'
                           % (KEYS[i], kind, n, KEYS[i], KEYS[i], inline(o)) for i, o in enumerate(options_of(item)))
            s.append('<fieldset class="opts" data-kind="%s"><legend class="ans-label">%s</legend>%s</fieldset>'
                     '<textarea class="ansinput is-choice" %s hidden aria-hidden="true" tabindex="-1"></textarea>' % (kind, hint, opts, box_attrs))
        elif qt == "output":
            s.append('<label class="ans-label" for="a%d">Exact output</label>'
                     '<textarea class="ansinput is-output" %s rows="2" spellcheck="false" autocomplete="off" placeholder="Type exactly what the program prints"></textarea>' % (n, box_attrs))
        else:
            s.append('<label class="ans-label" for="a%d">Your answer</label>'
                     '<textarea class="ansinput" %s rows="4" placeholder="Type your answer here..."></textarea>' % (n, box_attrs))
        s.append('<template class="model">%s</template></article>' % md2html(item["a"]))
        return "".join(s)

    def set_finish(self, key, total, label):
        return ('<div class="set-finish" data-for="%s"><div class="sf-status"><b class="sf-count">0 / %d answered</b>'
                '<span class="sf-score" hidden></span></div><div class="sf-actions">'
                '<button type="button" class="btn btn-primary js-compare">%s</button>'
                '<button type="button" class="btn btn-ghost js-edit" hidden>Edit my answers</button></div></div>') % (key, total, label)

    def question_page(self, mode):
        root = "../"; exam = mode == "exam"
        # answers are keyed by stable question id; data-legacy-store is the older number-keyed store, migrated once
        p = ['<div class="page qpage%s" data-store="%s" data-legacy-store="%s">' % (
            " exam" if exam else "", "prep.exam.v2" if exam else "prep.practice.v2", "prep.exam.v1" if exam else "prep.practice.v1")]
        p.append('<nav class="crumbs" aria-label="Breadcrumb"><a href="../index.html">Course</a><span aria-hidden="true">&rsaquo;</span>'
                 '<span aria-current="page">%s</span></nav>' % ("Exam sheet" if exam else "Question bank"))
        if exam:
            p.append('<header class="lesson-head"><div class="eyebrow"><span class="cat-tag">Practice exam</span><span>%d questions</span></div>'
                     '<h1>Exam sheet</h1><p class="lead">Answer every question in your own words; answers auto-save in this browser. '
                     'When you are done, press <b>Finish &amp; compare</b> to see your answers next to the model answers and mark each one. '
                     'You can also save your answers to a file and send it to be graded.</p></header>' % self.total_q)
            p.append('<div class="exambar" id="exambar"><div class="exam-row"><span id="prog" class="progpill" aria-live="polite">Answered 0 / %d</span>'
                     '<div class="bar exam-bar" role="progressbar" aria-label="Answered questions" aria-valuemin="0" aria-valuemax="%d" aria-valuenow="0"><span id="prog-bar"></span></div>'
                     '<div class="exam-actions"><button type="button" id="btn-next" class="btn btn-ghost btn-sm">Next unanswered</button>'
                     '<button type="button" id="btn-finish" class="btn btn-primary btn-sm" data-set="exam">Finish &amp; compare</button>'
                     '<button type="button" id="btn-download" class="btn btn-ghost btn-sm">&#11015; Save</button>'
                     '<label class="btn btn-ghost btn-sm" for="file-import">&#128194; Load<input id="file-import" type="file" accept=".md,.txt" hidden></label>'
                     '<button type="button" id="btn-clear" class="btn btn-ghost btn-sm">Clear</button></div></div>'
                     '<details class="qnav"><summary>Jump to question</summary><div class="qnav-grid" id="qnav">%s</div></details></div>'
                     % (self.total_q, self.total_q, "".join('<a href="#q%d" data-n="%d">%d</a>' % (n, n, n) for n in range(1, self.total_q + 1))))
            p.append('<div class="qset" data-set="exam">')
        else:
            p.append('<header class="lesson-head"><div class="eyebrow"><span class="cat-tag">Question bank</span><span>%d questions &middot; %d topics</span></div>'
                     '<h1>Question bank</h1><p class="lead">Write your answer to each question from memory. When a topic is done, press '
                     '<b>Compare my answers</b> to see yours next to the model answers, then mark how you did. Answers auto-save in this browser.</p>'
                     '<div class="lesson-actions"><a class="btn btn-ghost" href="exam-sheet.html">Switch to exam sheet &rarr;</a></div></header>' % (self.total_q, self.N))
            p.append('<div class="qfilter" role="group" aria-label="Filter by module"><button type="button" class="pill is-active" data-cat="all">All <span>%d</span></button>%s</div>'
                     % (self.total_q, "".join('<button type="button" class="pill" data-cat="%s">%s <span>%d</span></button>'
                                              % (cat_slug(c), esc(c), sum(self.qcount(t) for t in self.T if t["cat"] == c)) for c in self.cats)))
            p.append('<details class="jump"><summary>Jump to a topic</summary>%s</details>' % "".join(
                '<div class="jump-group"><b>%s</b>%s</div>' % (esc(label), "".join('<a href="#%s">%02d %s</a>' % (t["slug"], t["order"], esc(t["title"]))
                                                                              for t in items)) for c, label, items in self.runs()))
        for c, label, items in self.runs():
            p.append('<section class="qcat-block" data-cat="%s"><h2 class="qcat">%s</h2>' % (cat_slug(c), esc(label)))
            for t in items:
                p.append('<h3 class="qtopic" id="%s"><span class="n">%02d</span> %s <span class="count">&middot; %d Qs &middot; <a href="../html/%s.html">lesson</a></span></h3>'
                         % (t["slug"], t["order"], esc(t["title"]), self.qcount(t), fn(t)))
                if not exam: p.append('<div class="qset" data-set="%s">' % t["slug"])
                for item in t["quiz"]: p.append(self.qcard(item, t, mode))
                if not exam: p.append(self.set_finish(t["slug"], self.qcount(t), "Compare my answers") + "</div>")
            p.append("</section>")
        if exam: p.append(self.set_finish("exam", self.total_q, "Finish &amp; compare") + "</div>")
        p.append("</div>")
        scripts = ('<script src="../assets/legacy-qnums.js?v=%s"></script><script src="../assets/exam.js?v=%s" defer></script>'
                   '<script src="../assets/compare.js?v=%s" defer></script>') % (self.ver, self.ver, self.ver)
        return self.shell("%s — %s" % ("Exam sheet" if exam else "Question bank", SITE_TITLE), "\n".join(p), root,
                          active="exam" if exam else "qbank", kind="qbank" if not exam else "exam", extra_scripts=scripts)

    # --- progress + weak-spot practice (rendered in the browser from QMETA and the saved marks)
    def qmeta(self):
        """Question index for progress.js: topics in learning order and, per stable id, its number, topic and text."""
        topics = [{"s": t["slug"], "t": t["title"], "o": t["order"], "c": t["cat"], "ids": [q["id"] for q in t["quiz"]]}
                  for t in self.T if t.get("quiz")]
        qs = {q["id"]: {"n": q["n"], "s": t["slug"], "q": plain(q["q"]), "ty": q.get("type", "short")}
              for t in self.T for q in t.get("quiz", [])}
        return "window.QMETA=" + json.dumps({"topics": topics, "cats": self.cats, "q": qs, "max": PRACTICE_MAX}, ensure_ascii=False, separators=(",", ":")) + ";"

    def progress_page(self):
        root = "../"
        p = ['<div class="page qpage progress-page">',
             '<nav class="crumbs" aria-label="Breadcrumb"><a href="../index.html">Course</a><span aria-hidden="true">&rsaquo;</span><span aria-current="page">Progress</span></nav>',
             '<header class="lesson-head"><div class="eyebrow"><span class="cat-tag">Progress</span><span>%d questions</span></div>'
             '<h1>Progress</h1><p class="lead">Built from the marks you give when you compare answers (and the auto-scored questions). '
             'Weakest topics come first. Correct counts 1, Partly &frac12;, Missed 0.</p>'
             '<div class="lesson-actions"><a class="btn btn-primary" id="pg-practice" href="practice.html">Practice my weak spots &rarr;</a>'
             '<a class="btn btn-ghost" href="mocks.html">Mock exams</a>'
             '<a class="btn btn-ghost" href="master-question-sheet.html">Question bank</a></div></header>' % self.total_q,
             '<div id="pg-empty" class="pg-empty" hidden><b>No marks yet.</b> Answer some questions in the '
             '<a href="master-question-sheet.html">question bank</a> or the <a href="exam-sheet.html">exam sheet</a>, press compare, and mark them. Your progress shows up here.</div>',
             '<section class="stats pg-stats" id="pg-stats" aria-label="Overall"></section>',
             '<h2 class="section-title">Modules</h2><div class="pg-modules" id="pg-modules"></div>',
             '<h2 class="section-title">Topics <span class="pg-sub">weakest first</span></h2><div class="pg-topics" id="pg-topics"></div>',
             '<h2 class="section-title">Questions to revisit <span class="pg-sub">missed first, then partly</span></h2><div class="pg-weak" id="pg-weak"></div>',
             '<p class="foot-note">Marks are stored only in this browser. <button type="button" class="linkbtn" id="pg-reset">Reset all marks</button></p>',
             '</div>']
        scripts = '<script src="../assets/qmeta.js?v=%s"></script><script src="../assets/progress.js?v=%s" defer></script>' % (self.ver, self.ver)
        return self.shell("Progress — %s" % SITE_TITLE, "\n".join(p), root, active="progress", kind="progress", extra_scripts=scripts)

    def practice_page(self):
        """Every question is rendered hidden; progress.js reveals the weak ones as a single compare set."""
        root = "../"
        p = ['<div class="page qpage practice-page" data-store="prep.weak.v1">',
             '<nav class="crumbs" aria-label="Breadcrumb"><a href="../index.html">Course</a><span aria-hidden="true">&rsaquo;</span>'
             '<a href="progress.html">Progress</a><span aria-hidden="true">&rsaquo;</span><span aria-current="page">Practice weak spots</span></nav>',
             '<header class="lesson-head"><div class="eyebrow"><span class="cat-tag">Weak-spot practice</span><span id="pr-scope">All topics</span></div>'
             '<h1>Practice my weak spots</h1><p class="lead">Questions you marked <b>Missed</b> come first, then <b>Partly</b> (up to %d at a time). '
             'Answer them again, compare, and mark them. Each one you now get right drops off the list.</p>'
             '<div class="lesson-actions"><button type="button" class="btn btn-ghost" id="pr-new">Start a new round</button>'
             '<a class="btn btn-ghost" href="progress.html">Back to progress</a></div></header>' % PRACTICE_MAX,
             '<div id="pr-empty" class="pg-empty" hidden></div>',
             '<div class="qset" data-set="practice">']
        for t in self.T:
            for item in t.get("quiz", []):
                p.append(self.qcard(item, t, "practice").replace('<article class="qcard"', '<article hidden class="qcard"', 1))
        p.append(self.set_finish("practice", 0, "Compare my answers") + "</div></div>")
        scripts = ('<script src="../assets/qmeta.js?v=%s"></script><script src="../assets/progress.js?v=%s"></script>'
                   '<script src="../assets/exam.js?v=%s" defer></script><script src="../assets/compare.js?v=%s" defer></script>') % ((self.ver,) * 4)
        return self.shell("Practice weak spots — %s" % SITE_TITLE, "\n".join(p), root, active="practice", kind="practice", extra_scripts=scripts)

    # --- mock exams
    def mocks_page(self):
        root = "../"
        cards = []
        for m in self.mocks:
            pick = self.mock_picks[m["id"]]
            auto = sum(1 for _, q in pick if q.get("type", "short") in AUTO_TYPES)
            scope = "Whole course" if m.get("lessons") is None else "Lessons " + ", ".join(
                ("%02d" % lo) if lo == hi else "%02d&ndash;%02d" % (lo, hi) for lo, hi in m["lessons"])
            cards.append('<section class="mock-card" data-mock="%s"><div class="mock-top"><span class="mock-kind %s">%s</span><span class="mock-scope">%s</span></div>'
                         '<h3>%s</h3><div class="module-meta"><span>%d questions</span><span>%d minutes</span><span>%d auto-scored</span></div>'
                         '<div class="mock-stats" data-mock-stats="%s">Not taken yet</div>'
                         '<a class="btn btn-primary mock-go" href="mock-%s.html">Start &rarr;</a></section>'
                         % (m["id"], m["kind"].lower(), esc(m["kind"]), scope, esc(m["title"]), m["questions"], m["minutes"], auto, m["id"], m["id"]))
        p = ['<div class="page qpage mocks-page">',
             '<nav class="crumbs" aria-label="Breadcrumb"><a href="../index.html">Course</a><span aria-hidden="true">&rsaquo;</span><span aria-current="page">Mock exams</span></nav>',
             '<header class="lesson-head"><div class="eyebrow"><span class="cat-tag">Mock exams</span><span>%d mocks</span></div>'
             '<h1>Mock exams</h1><p class="lead">Timed, exam conditions: no model answers until you submit (or time runs out). '
             'Then auto-scored questions are marked for you, and you mark the written ones. Every mark also feeds your '
             '<a href="progress.html">progress</a>. <b>Quick</b> mocks: 20 questions in 30 minutes. <b>Full</b> mocks: 40 in 60.</p></header>' % len(self.mocks),
             '<div class="mock-grid">%s</div>' % "".join(cards),
             '<p class="foot-note">Each mock keeps the same questions every time, so your scores are comparable across attempts. Attempts are stored only in this browser.</p></div>']
        scripts = '<script src="../assets/mock.js?v=%s" defer></script>' % self.ver
        return self.shell("Mock exams — %s" % SITE_TITLE, "\n".join(p), root, active="mocks", kind="mocks", extra_scripts=scripts)

    def mock_page(self, m):
        root = "../"; pick = self.mock_picks[m["id"]]; N = len(pick)
        p = ['<div class="page qpage mock-page" data-store="prep.mock.%s.v1" data-mock="%s" data-minutes="%d">' % (m["id"], m["id"], m["minutes"]),
             '<nav class="crumbs" aria-label="Breadcrumb"><a href="../index.html">Course</a><span aria-hidden="true">&rsaquo;</span>'
             '<a href="mocks.html">Mock exams</a><span aria-hidden="true">&rsaquo;</span><span aria-current="page">%s</span></nav>' % esc(m["title"]),
             '<header class="lesson-head"><div class="eyebrow"><span class="mock-kind %s">%s mock</span><span>%d questions &middot; %d minutes</span></div>'
             '<h1>%s</h1></header>' % (m["kind"].lower(), esc(m["kind"]), N, m["minutes"], esc(m["title"])),
             # start screen
             '<section class="mock-intro" id="mock-intro"><h2>Before you start</h2><ul>'
             '<li>%d questions, %d minutes. The clock keeps running if you leave or reload the page.</li>'
             '<li>No model answers until you submit. When time runs out, your answers are submitted automatically.</li>'
             '<li>After submitting, auto-scored questions are marked for you; you mark the written ones Correct / Partly / Missed.</li></ul>'
             '<button type="button" class="btn btn-primary btn-lg" id="mock-start">Start the mock &rarr;</button></section>' % (N, m["minutes"]),
             # running bar
             '<div class="exambar mockbar" id="mockbar" hidden><div class="exam-row">'
             '<span class="timer" id="mock-timer" role="timer" aria-live="off">--:--</span>'
             '<span id="prog" class="progpill" aria-live="polite">Answered 0 / %d</span>'
             '<div class="bar exam-bar" role="progressbar" aria-label="Answered questions" aria-valuemin="0" aria-valuemax="%d" aria-valuenow="0"><span id="prog-bar"></span></div>'
             '<div class="exam-actions"><button type="button" class="btn btn-primary btn-sm" id="mock-submit">Submit</button></div></div></div>' % (N, N),
             # results
             '<section class="mock-result" id="mock-result" hidden><div class="mr-score"><b id="mr-score">&ndash;</b><span id="mr-pct"></span></div>'
             '<div class="mr-lines"><span id="mr-time"></span><span id="mr-auto"></span><span id="mr-written"></span></div>'
             '<div class="lesson-actions"><button type="button" class="btn btn-ghost" id="mock-retake">Retake this mock</button>'
             '<a class="btn btn-ghost" href="mocks.html">All mocks</a><a class="btn btn-ghost" href="progress.html">Progress</a></div></section>',
             '<div id="mock-body" hidden><div class="qset" data-set="mock">']
        for k, (t, item) in enumerate(pick):
            p.append(self.qcard(item, t, "mock", label="Question %d of %d" % (k + 1, N)))
        p.append(self.set_finish("mock", N, "Compare my answers") + '</div></div></div>')
        scripts = ('<script src="../assets/exam.js?v=%s" defer></script><script src="../assets/compare.js?v=%s" defer></script>'
                   '<script src="../assets/mock.js?v=%s" defer></script>') % ((self.ver,) * 3)
        return self.shell("%s — Mock exam — %s" % (m["title"], SITE_TITLE), "\n".join(p), root, active="mocks", kind="mock", extra_scripts=scripts)

    # --- markdown copies
    def topic_md(self, t):
        L = ["# %02d — %s" % (t["order"], t["title"]), "", "*Category: %s*" % t["cat"], "", "> %s" % t["summary"], "", "## Must-remember points", ""]
        for x in t["points"]: L.append("- %s" % x)
        L.append("")
        for h, body in t.get("detail", []): L += ["## %s" % h, "", body, ""]
        if t.get("confuse"):
            L += ["## ⚠ Easily confused", ""]
            for a, d in t["confuse"]: L.append("- **%s** — %s" % (a, d))
            L.append("")
        L.append("➡ Questions for this topic: `questions/master-question-sheet.md` (section %02d)." % t["order"])
        return "\n".join(L)

    def questions_md(self):
        qm = ["# Master Question Bank", "",
              "%d single-focus questions across %d topics, in learning order. Each question asks one thing; the answer is hidden in a <details> block." % (self.total_q, self.N), ""]
        for c, label, items in self.runs():
            qm += ["## %s" % label, ""]
            for t in items:
                qm.append("### %02d — %s  (%d Qs)" % (t["order"], t["title"], self.qcount(t)))
                for item in t["quiz"]:
                    qm += ["**Q%d. %s**" % (item["n"], item["q"]), ""]
                    note = show_note(item)
                    if note: qm += [note, ""]
                    qt = item.get("type", "short"); key = ""
                    if qt in CHOICE_TYPES:
                        qm += ["- **%s)** %s" % (KEYS[i], o) for i, o in enumerate(options_of(item))] + [""]
                        key = "**Correct: %s**\n\n" % ", ".join(KEYS[i] for i in correct_indices(item))
                    elif qt == "output":
                        key = "**Expected output:**\n```\n%s\n```\n\n" % item["expected"]
                    qm += ["<details><summary>Show answer</summary>", "", key + item["a"], "", "</details>", ""]
        return "\n".join(qm)

    # --- search index (loaded as a script so it works from file://)
    def search_index(self):
        idx = []
        for t in self.T:
            idx.append({"k": "lesson", "t": "%02d %s" % (t["order"], t["title"]), "c": t["cat"], "u": "html/%s.html" % fn(t),
                        "x": t["summary"] + " " + " ".join(plain(x) for x in t["points"])
                             + " " + " ".join(plain(h) for h, _ in t.get("detail", []))
                             + " " + " ".join(plain(a) for a, _ in t.get("confuse", []))})
            for q in t.get("quiz", []):
                idx.append({"k": "question", "t": plain(q["q"]), "c": "%02d %s" % (t["order"], t["title"]),
                            "u": "questions/master-question-sheet.html#q%d" % q["n"], "x": " ".join(q.get("concepts", []) + q.get("tags", []))})
        for k, e in EXTRAS.items():
            idx.append({"k": "deep dive", "t": e["title"], "c": "Deep dive", "u": "extras/" + e["file"], "x": e["blurb"]})
        return "window.SEARCH_INDEX=" + json.dumps(idx, ensure_ascii=False, separators=(",", ":")) + ";"

# ---------------------------------------------------------------- build
# pairs of question ids that are allowed to look alike (same wording is intentional, or a known duplicate kept for now)
SIMILAR_OK = set()
_STOP = set("the a an is of in to and or what does do this that why how you it for on be are with your".split())
def _tokens(item):
    text = (item["q"] + " " + (show_note(item) or "")).lower().replace("`", "")
    return set(re.findall(r"[a-z0-9_:+<>*&=!-]+", text)) - _STOP

def check_questions(S):
    """Build fails on malformed questions so they never reach the site."""
    errs = []; seen = {}
    allq = [(t, q) for t in S.T for q in t.get("quiz", [])]
    for t, q in allq:
        where = "%s (Q%d)" % (q["id"], q["n"]); qt = q.get("type", "short")
        if q["id"] in seen: errs.append("%s: duplicate id (also Q%d)" % (where, seen[q["id"]]))
        seen[q["id"]] = q["n"]
        if qt not in QTYPES: errs.append("%s: unknown type %r (use one of %s)" % (where, qt, ", ".join(QTYPES))); continue
        if not (q.get("a") or "").strip(): errs.append("%s: missing model answer / explanation" % where)
        if qt in ("mcq", "multi"):
            opts = q.get("options") or []
            if len(opts) < 2 or len(opts) > len(KEYS): errs.append("%s: needs 2-%d options" % (where, len(KEYS)))
            c = q.get("correct")
            idx = c if isinstance(c, (list, tuple)) else [c]
            if not idx or not all(isinstance(i, int) and 0 <= i < len(opts) for i in idx): errs.append("%s: correct must be option index(es) 0..%d" % (where, len(opts) - 1))
            elif qt == "mcq" and len(idx) != 1: errs.append("%s: mcq has exactly one correct option (use type='multi' for more)" % where)
            elif len(set(idx)) != len(idx): errs.append("%s: correct lists an option twice" % where)
            if len(set(o.strip().lower() for o in opts)) != len(opts): errs.append("%s: two options are identical" % where)
        if qt == "tf" and not isinstance(q.get("correct"), bool): errs.append("%s: tf needs correct=True or correct=False" % where)
        if qt == "output" and not (isinstance(q.get("expected"), str) and q["expected"].strip()): errs.append("%s: output needs expected='...'" % where)
    toks = [(q, _tokens(q)) for _, q in allq]
    for i in range(len(toks)):
        for j in range(i + 1, len(toks)):
            a, b = toks[i][1], toks[j][1]
            if a and b and len(a & b) / len(a | b) >= 0.85 and frozenset({toks[i][0]["id"], toks[j][0]["id"]}) not in SIMILAR_OK:
                errs.append("near-duplicate questions: %s (Q%d) and %s (Q%d) -> reword one, or add the pair to SIMILAR_OK"
                            % (toks[i][0]["id"], toks[i][0]["n"], toks[j][0]["id"], toks[j][0]["n"]))
    if errs:
        print("\nQUESTION CHECK FAILED (%d):" % len(errs))
        for e in errs: print("  -", e)
        raise SystemExit(1)

AUTO_TYPES = ("output",) + CHOICE_TYPES

MOCK_AUTO_SHARE = 0.5      # a mock aims for about this share of auto-scored questions (the rest are written)

def pick_mock(S, m, picked):
    """Deterministic question pick for one mock (see MOCKS in gen_study.py). Returns [(topic, question)].
    Round-robin over the mock's topics (shuffled), one question per topic per round; each pick takes an auto-scored
    or a written question, whichever keeps the mix closest to MOCK_AUTO_SHARE (falling back to what the topic has).
    Questions used by the mock named in `avoid` go last."""
    rng = random.Random(m["id"])                     # str seed -> same sequence on every run and machine
    share = m.get("auto_share", MOCK_AUTO_SHARE)
    def in_scope(t): return m.get("lessons") is None or any(lo <= t["order"] <= hi for lo, hi in m["lessons"])
    def is_auto(q): return q.get("type", "short") in AUTO_TYPES
    topics = [t for t in S.T if t.get("quiz") and in_scope(t)]
    avoid = set(picked.get(m.get("avoid"), []))
    queues = []
    for t in topics:
        qs = list(t["quiz"]); rng.shuffle(qs)
        qs.sort(key=lambda q: q["id"] in avoid)      # stable: keeps the shuffle, avoided ones last
        queues.append((t, qs))
    rng.shuffle(queues)
    out = []; autos = 0
    while len(out) < m["questions"] and any(qs for _, qs in queues):
        for t, qs in queues:
            if not qs or len(out) >= m["questions"]: continue
            want_auto = autos < share * (len(out) + 1)
            fresh = [q for q in qs if q["id"] not in avoid] or qs
            q = next((q for q in fresh if is_auto(q) == want_auto), fresh[0])
            qs.remove(q); out.append((t, q)); autos += is_auto(q)
    if len(out) < m["questions"]:
        raise SystemExit("mock %s wants %d questions but its lessons only have %d" % (m["id"], m["questions"], len(out)))
    rng.shuffle(out)
    return out

def check_mocks(mocks):
    ids = [m["id"] for m in mocks]
    errs = ["duplicate mock id " + i for i in set(ids) if ids.count(i) > 1]
    for m in mocks:
        if not re.match(r"^[a-z0-9-]+$", m["id"]): errs.append("mock id %r: use a-z, 0-9 and -" % m["id"])
        if m.get("avoid") and m["avoid"] not in ids[:ids.index(m["id"])]: errs.append("mock %s: avoid=%r must name an earlier mock" % (m["id"], m["avoid"]))
        if not (m.get("questions", 0) > 0 and m.get("minutes", 0) > 0): errs.append("mock %s: needs questions > 0 and minutes > 0" % m["id"])
    if errs:
        print("\nMOCK CHECK FAILED:"); [print("  -", e) for e in errs]; raise SystemExit(1)

def load_legacy(here):
    """Frozen map of question number -> stable id from before answers were keyed by id (see exam.js migrate())."""
    with open(os.path.join(here, "legacy_qnums.json"), encoding="utf-8") as f: return json.load(f)

def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f: f.write(text)

def build(topics, here, mocks=()):
    out = os.path.join(here, "site")
    if os.path.isdir(out): shutil.rmtree(out)
    S = Site(topics)
    check_questions(S)
    check_mocks(mocks)
    S.mocks = list(mocks)
    for m in S.mocks: S.mock_picks[m["id"]] = pick_mock(S, m, {k: [q["id"] for _, q in v] for k, v in S.mock_picks.items()})
    # cache-busting: pages link assets as style.css?v=<hash>, so a browser never pairs new HTML with an old cached script
    h = hashlib.sha1(S.search_index().encode("utf-8") + S.qmeta().encode("utf-8") + json.dumps(load_legacy(here)).encode("utf-8")
                     + json.dumps({k: [q["id"] for _, q in v] for k, v in S.mock_picks.items()}).encode("utf-8"))
    for f in ("style.css", "app.js", "exam.js", "compare.js", "progress.js", "mock.js"):
        with open(os.path.join(here, "site_src", f), "rb") as fh: h.update(fh.read())
    S.ver = h.hexdigest()[:10]
    # unique-order / unique-slug guard
    orders = [t["order"] for t in S.T]; slugs = [t["slug"] for t in S.T]
    assert len(set(orders)) == len(orders), "duplicate topic order"
    assert len(set(slugs)) == len(slugs), "duplicate topic slug"
    for i, t in enumerate(S.T):
        write(os.path.join(out, "html", fn(t) + ".html"), S.lesson(i))
        write(os.path.join(out, "md", fn(t) + ".md"), S.topic_md(t))
    write(os.path.join(out, "index.html"), S.home())
    write(os.path.join(out, "questions", "master-question-sheet.html"), S.question_page("bank"))
    write(os.path.join(out, "questions", "exam-sheet.html"), S.question_page("exam"))
    write(os.path.join(out, "questions", "progress.html"), S.progress_page())
    write(os.path.join(out, "questions", "practice.html"), S.practice_page())
    write(os.path.join(out, "questions", "mocks.html"), S.mocks_page())
    for m in S.mocks: write(os.path.join(out, "questions", "mock-%s.html" % m["id"]), S.mock_page(m))
    write(os.path.join(out, "assets", "qmeta.js"), S.qmeta())
    write(os.path.join(out, "questions", "master-question-sheet.md"), S.questions_md())
    write(os.path.join(out, "assets", "search-index.js"), S.search_index())
    write(os.path.join(out, "assets", "legacy-qnums.js"), "window.LEGACY_QNUMS=" + json.dumps(load_legacy(here), separators=(",", ":")) + ";")
    for f in ("style.css", "app.js", "exam.js", "compare.js", "progress.js", "mock.js"):
        shutil.copyfile(os.path.join(here, "site_src", f), os.path.join(out, "assets", f))
    os.makedirs(os.path.join(out, "extras"), exist_ok=True)
    for e in EXTRAS.values():
        src = os.path.join(here, "extras", e["file"])
        if not os.path.isfile(src): raise SystemExit("missing standalone page: " + src)
        os.makedirs(os.path.join(out, "extras"), exist_ok=True)
        shutil.copyfile(src, os.path.join(out, "extras", e["file"]))
    print("topics: %d  questions: %d  (avg %.1f/topic)" % (S.N, S.total_q, S.total_q / S.N))
    for d in ("html", "md", "questions", "extras", "assets"):
        print("  site/%-9s %d files" % (d, len(os.listdir(os.path.join(out, d)))))
    import validate_site
    return validate_site.run(out, S)
