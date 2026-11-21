# -*- coding: utf-8 -*-
"""Compile (and run) every C++ code block in the lessons, and compare each program's real output with the ```output
block shown under it.

    python3 check_code.py              (all lessons; needs g++; exits non-zero on any problem)
    python3 check_code.py libraries    (only the lessons whose slug contains this text)

Rules for lesson code blocks (sections in `detail`):
  * ```cpp with `int main(`  -> must compile as-is (its own #includes) with g++ -std=c++17 -Wall -Wextra, and is run.
    If the very next block is ```output, the program's stdout must match it (trailing spaces ignored).
  * A block containing the words "does not compile" must FAIL to compile (that is its point).
  * A block whose comments say "undefined behaviour" (or "(not run)") is compiled but not run; no ```output after it.
  * ```cpp without main = a fragment: must compile with common headers added (as a file, or inside a main).
  * "C++20" anywhere in a block -> compiled with -std=c++20.
  * ```output must follow a runnable ```cpp block or a ```bash block (shell sessions are not run).
  * ```text = "Example output" (differs per machine or run): shown, never compared.
Not part of the site build. Run it after adding or editing lesson code, next to check_outputs.py (which checks the
quiz's "predict the output" questions).
"""
import os, re, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
HEADERS = ("#include <iostream>\n#include <string>\n#include <vector>\n#include <array>\n#include <memory>\n#include <utility>\n"
           "#include <stdexcept>\n#include <map>\n#include <algorithm>\n#include <cstring>\n#include <cstdint>\n#include <tuple>\n")
FENCE = re.compile(r"```(\w*)\n(.*?)```", re.S)


def load_topics():
    src = open(os.path.join(HERE, "gen_study.py"), encoding="utf-8").read().split('if __name__ == "__main__":')[0]
    ns = {"__file__": os.path.join(HERE, "gen_study.py")}
    exec(compile(src, "gen_study.py", "exec"), ns)
    return ns["T"]


def norm(s):
    return "\n".join(l.rstrip() for l in s.replace("\r\n", "\n").split("\n")).strip()


def gpp(src, std, d, run=True):
    f, exe = os.path.join(d, "t.cpp"), os.path.join(d, "t")
    open(f, "w").write(src)
    c = subprocess.run(["g++", "-std=" + std, "-Wall", "-Wextra", "-pthread", "-o", exe, f], capture_output=True, text=True,
                       env=dict(os.environ, LC_ALL="C"))
    if c.returncode or not run:
        return c.returncode, c.stderr, None
    return 0, c.stderr, subprocess.run([exe], capture_output=True, text=True, timeout=10).stdout


def check_body(where, body, d):
    errs, blocks, prev = [], [(m.group(1).lower(), m.group(2)) for m in FENCE.finditer(body)], None
    for k, (lang, code) in enumerate(blocks, 1):
        tag = "%s, block %d (%s)" % (where, k, lang or "plain")
        if lang == "output":
            if prev is None: errs.append(tag + ": output block without a runnable program or shell session above it")
            elif prev != "bash" and norm(prev) != norm(code): errs.append("%s: shown %r, program prints %r" % (tag, norm(code), norm(prev)))
            prev = None; continue
        prev = "bash" if lang in ("bash", "sh") else None
        if lang not in ("cpp", "c"): continue
        std = "c++20" if "C++20" in code else "c++17"
        has_main = re.search(r"\bint\s+main\s*\(", code) is not None
        if "does not compile" in code.lower():
            rc = gpp(code if has_main else HEADERS + code, std, d, run=False)[0]
            if rc == 0 and not has_main: rc = gpp(HEADERS + "int main() {\n" + code + "\n}\n", std, d, run=False)[0]
            if rc == 0: errs.append(tag + ": marked 'does not compile' but it compiles")
            continue
        if has_main:
            no_run = re.search(r"undefined behaviou?r|\(not run\)", code, re.I) is not None
            rc, err, out = gpp(code, std, d, run=not no_run)
            if rc: errs.append("%s: does not compile\n%s" % (tag, "\n".join(err.split("\n")[:8]))); continue
            if not no_run: prev = out
        elif gpp(HEADERS + code + "\nint main(){}\n", std, d, run=False)[0] and gpp(HEADERS + "int main() {\n" + code + "\n}\n", std, d, run=False)[0]:
            errs.append(tag + ": fragment does not compile")
    return errs, sum(1 for l, _ in blocks if l in ("cpp", "c"))


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    bad = n = 0
    with tempfile.TemporaryDirectory() as d:
        for t in sorted(load_topics(), key=lambda t: t["order"]):
            if only not in t["slug"]: continue
            for h, body in t.get("detail", []):
                errs, k = check_body("%02d %s / %s" % (t["order"], t["slug"], h), body, d)
                n += k; bad += len(errs)
                for e in errs: print("  X ", e)
    print("lesson code blocks: %d checked, %d problem(s)" % (n, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
