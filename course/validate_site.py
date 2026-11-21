# -*- coding: utf-8 -*-
"""Post-build checks for ./site. Called by gen_study.py; can also be run alone:
    python3 validate_site.py            (re-parses site/ and checks structure + every internal link)
Exits non-zero on any error so a broken build is never silent."""
import os, re, sys
from html.parser import HTMLParser

class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids = set(); self.refs = []; self.dup = []; self.title = None; self._t = False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            if a["id"] in self.ids: self.dup.append(a["id"])
            self.ids.add(a["id"])
        if tag == "a" and a.get("href"): self.refs.append(("href", a["href"]))
        if tag in ("script", "img") and a.get("src"): self.refs.append(("src", a["src"]))
        if tag == "link" and a.get("href"): self.refs.append(("href", a["href"]))
        if tag == "title": self._t = True
    def handle_endtag(self, tag):
        if tag == "title": self._t = False
    def handle_data(self, d):
        if self._t: self.title = (self.title or "") + d

def run(out, S=None):
    errs = []; pages = {}
    for dp, _, fs in os.walk(out):
        for f in fs:
            if f.endswith(".html"):
                p = os.path.join(dp, f); parser = P()
                parser.feed(open(p, encoding="utf-8").read()); pages[os.path.abspath(p)] = parser
    nlinks = 0
    for path, pr in pages.items():
        rel = os.path.relpath(path, out)
        if rel.startswith("extras"): continue          # standalone pages are intentionally left untouched
        if not pr.title: errs.append("%s: missing <title>" % rel)
        for d in set(pr.dup): errs.append("%s: duplicate id %r" % (rel, d))
        for kind, ref in pr.refs:
            if re.match(r"(https?:|mailto:|javascript:|data:)", ref): errs.append("%s: external/unsafe ref %s" % (rel, ref)); continue
            nlinks += 1
            target, _, frag = ref.partition("#")
            target = target.partition("?")[0]          # asset links carry ?v=<hash> for cache-busting
            tpath = os.path.abspath(os.path.join(os.path.dirname(path), target)) if target else path
            if not os.path.exists(tpath): errs.append("%s: broken link -> %s" % (rel, ref)); continue
            if frag and tpath.endswith(".html"):
                tp = pages.get(tpath)
                if tp is None or frag not in tp.ids: errs.append("%s: missing anchor -> %s" % (rel, ref))
    if S is not None:
        # structure: every topic has a page + md; prev/next chain; every lesson's test link hits its question section
        for i, t in enumerate(S.T):
            name = "%02d-%s" % (t["order"], t["slug"])
            lp = os.path.join(out, "html", name + ".html")
            if not os.path.exists(lp) or not os.path.exists(os.path.join(out, "md", name + ".md")): errs.append("missing page/md for " + name)
            elif t.get("quiz") is not None:
                q = pages[os.path.abspath(os.path.join(out, "questions", "master-question-sheet.html"))]
                if t["slug"] not in q.ids: errs.append("question sheet has no section id for " + t["slug"])
            text = open(lp, encoding="utf-8").read()
            pv = re.search(r'rel="prev" href="([^"]+)"|href="([^"]+)" rel="prev"', text)
            nx = re.search(r'rel="next"[^>]*href="([^"]+)"|href="([^"]+)" rel="next"', text)
            want_prev = ("%02d-%s.html" % (S.T[i-1]["order"], S.T[i-1]["slug"])) if i else "../index.html"
            want_next = ("%02d-%s.html" % (S.T[i+1]["order"], S.T[i+1]["slug"])) if i < S.N - 1 else "../questions/master-question-sheet.html"
            gp = (pv.group(1) or pv.group(2)) if pv else None; gn = (nx.group(1) or nx.group(2)) if nx else None
            if gp != want_prev: errs.append("%s: prev link %s != %s" % (name, gp, want_prev))
            if gn != want_next: errs.append("%s: next link %s != %s" % (name, gn, want_next))
        qs = pages[os.path.abspath(os.path.join(out, "questions", "master-question-sheet.html"))]
        ex = pages[os.path.abspath(os.path.join(out, "questions", "exam-sheet.html"))]
        for n in range(1, S.total_q + 1):
            if "q%d" % n not in qs.ids: errs.append("question bank missing q%d" % n)
            if "q%d" % n not in ex.ids: errs.append("exam sheet missing q%d" % n)
        # search index: every url resolves (incl. #anchor)
        idx = open(os.path.join(out, "assets", "search-index.js"), encoding="utf-8").read()
        for u in re.findall(r'"u":"([^"]+)"', idx):
            target, _, frag = u.partition("#"); tp = os.path.abspath(os.path.join(out, target))
            if not os.path.exists(tp): errs.append("search index: missing file " + u)
            elif frag and tp.endswith(".html") and (tp not in pages or frag not in pages[tp].ids): errs.append("search index: missing anchor " + u)
        # stable ids: every id answers were ever saved under must still exist (append new questions at the END of a topic)
        import json
        legacy = json.load(open(os.path.join(os.path.dirname(out), "legacy_qnums.json"), encoding="utf-8"))
        ids = {q["id"] for t in S.T for q in t.get("quiz", [])}
        for num, qid in legacy.items():
            if qid not in ids: errs.append("question id %s (old Q%s) no longer exists; saved answers would be orphaned" % (qid, num))
    print("validated %d pages, %d internal links" % (len(pages), nlinks))
    if errs:
        print("\nVALIDATION FAILED (%d):" % len(errs))
        for e in errs[:40]: print("  -", e)
        return 1
    print("validation OK")
    return 0

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    sys.exit(run(os.path.join(here, "site")))
