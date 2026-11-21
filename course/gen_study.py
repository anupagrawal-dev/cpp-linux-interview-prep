# -*- coding: utf-8 -*-
"""Study course content (the source of truth) + build entry point.

Run:  python3 gen_study.py        ->  writes the static site into ./site/

Layout produced (all links relative, works from file:// with no server):
  site/index.html                      course home / dashboard
  site/html/NN-slug.html               one lesson per topic
  site/md/NN-slug.md                   Markdown copy of each lesson
  site/questions/master-question-sheet.html / .md
  site/questions/exam-sheet.html
  site/extras/*.html                   standalone deep-dive pages (copied from ./extras/)
  site/assets/                         style.css, app.js, exam.js, search-index.js (from ./site_src/)

To add a topic: append a topic(...) entry below with the next `order`, then re-run.
Engine (rendering, search index, validation) lives in sitegen.py; design in site_src/.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# ---------- content ----------
def Q(q, a, note=None, explain=None, **meta):
    """Question. Optional metadata (id, type, difficulty, level, options, correct, concepts, tags, prereq, mock)
    is carried through to the search index and the assessment engine."""
    d = {"q":q, "a":a, "note":note, "explain":explain}; d.update(meta); return d
# NOTE POLICY: a note is shown with the question ONLY when it is a code snippet that
# the question is about (e.g. "what does this print?"). Plain-text hints are NOT shown
# (no answer hints). `explain` = an optional clarification of what the question is ASKING
# (never a hint toward the answer); it is shown behind its own small button, only when set.
def show_note(item):
    n = item.get("note")
    return n if (n and n.strip().startswith("```")) else None
T=[]
def topic(**k): T.append(k)


# ===== Lessons: append each new topic(...) below, with the next `order` =====


# ===== Extra questions for existing lessons =====
# Always APPEND to a topic: answers are saved by question id (slug-NN by position), so inserting in the middle
# would move them. The build checks that every id answers were saved under still exists.
def add_questions(slug, *qs):
    next(t for t in T if t["slug"] == slug)["quiz"].extend(qs)

# Timed mock exams, added once there are enough lessons, e.g.
# dict(id="quick-1", kind="Quick", title="C++ Core", lessons=[(1, 10)], questions=20, minutes=30)
MOCKS = []

if __name__ == "__main__":
    import sitegen
    sys.exit(sitegen.build(T, HERE, MOCKS))
