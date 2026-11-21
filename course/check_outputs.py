# -*- coding: utf-8 -*-
"""Compile and run every C++ "predict the output" question and compare with its `expected` answer.

    python3 check_outputs.py          (needs g++; exits non-zero on any mismatch)

A snippet without `main` is wrapped in one. Standard headers are added up front, so snippets can stay short.
Bash snippets are listed but not run (they depend on the machine's directories).
Not part of the site build: run it after adding or editing output questions.
"""
import os, re, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
HEADERS = ("#include <iostream>\n#include <vector>\n#include <array>\n#include <string>\n#include <memory>\n#include <stdexcept>\n"
           "#include <utility>\n#include <map>\n#include <algorithm>\n#include <cstring>\n#include <cstdint>\n#include <tuple>\n")

def load_topics():
    sys.path.insert(0, HERE)
    src = open(os.path.join(HERE, "gen_study.py"), encoding="utf-8").read().split('if __name__ == "__main__":')[0]
    ns = {"__file__": os.path.join(HERE, "gen_study.py")}
    exec(compile(src, "gen_study.py", "exec"), ns)
    return ns["T"]

def norm(s):
    return "\n".join(l.rstrip() for l in s.replace("\r\n", "\n").split("\n")).strip()

def main():
    topics = sorted(load_topics(), key=lambda t: t["order"])
    ok = bad = skipped = 0
    with tempfile.TemporaryDirectory() as d:
        for t in topics:
            for k, q in enumerate(t.get("quiz", [])):
                if q.get("type") != "output": continue
                qid = q.get("id") or "%s-%02d" % (t["slug"], k + 1)
                m = re.search(r"```(\w*)\n(.*?)```", q.get("note") or "", re.S)
                if not m: print("  ?  %s: no code block" % qid); bad += 1; continue
                lang, code = m.group(1), m.group(2)
                if lang not in ("cpp", "c"): print("  -  %s: %s snippet, not run" % (qid, lang or "plain")); skipped += 1; continue
                body = code if re.search(r"\bint\s+main\s*\(", code) else "int main() {\n%s\n}\n" % code
                src = os.path.join(d, "q.cpp"); exe = os.path.join(d, "q")
                open(src, "w").write(HEADERS + body)
                c = subprocess.run(["g++", "-std=c++17", "-w", "-o", exe, src], capture_output=True, text=True)
                if c.returncode: print("  X  %s: does not compile\n%s" % (qid, c.stderr[:400])); bad += 1; continue
                out = subprocess.run([exe], capture_output=True, text=True, timeout=10).stdout
                if norm(out) == norm(q["expected"]): ok += 1
                else: print("  X  %s: printed %r, expected %r" % (qid, out, q["expected"])); bad += 1
    print("output questions: %d match, %d wrong, %d not run" % (ok, bad, skipped))
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
