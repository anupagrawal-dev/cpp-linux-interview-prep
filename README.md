# cpp-linux-interview-prep

My C++ and Linux systems interview preparation: a four-month study plan, and a revision course built from what I learned along the way.

The aim is to be interview-ready for C++ / Linux systems roles: C++11/14 in depth (core language, memory, OOP, templates, STL, concurrency), plus Linux processes and threads, TCP and sockets, and security basics. C++17/20/23 come after this plan.

## How each topic is learned

1. Watch the day's videos.
2. Write down my own points.
3. Expand them into a complete topic: every point plus whatever I missed, one point at a time, each with a complete program and its real output.
4. Go deeper, with another example, on anything still unclear.
5. Answer 2–3 interview-style questions on it.
6. Only when I am satisfied, save the topic here as a lesson.

A topic counts as done only when I can explain it.

## What is in this repo

```
course/      the revision course: lessons, questions, site generator, code checks
  site/      the generated course pages (open site/index.html in a browser)
builds/      the weekly build exercises, one folder per week
README.md    this file
```

Each lesson has a short list of key concepts, one section per subtopic (meaning, a complete runnable program, its real output, how it works), the common mistakes, and practice questions. Every program in a lesson is compiled with g++, and the output shown is the real output.

## Building the course

```bash
cd course
python3 gen_study.py      # regenerates site/ and checks the questions and links
python3 check_code.py     # compiles every lesson program and compares its output
python3 check_outputs.py  # compiles and runs every "predict the output" question
```

Needs Python 3 and g++. The site works offline straight from the folder: no server, no internet.

## The plan

Weekdays are short (office) evenings for C++ only, Thursday adds Linux, Friday adds networking and security; Saturday is a build plus LeetCode; Sunday is revision.

| Week | Dates | Focus |
|---|---|---|
| 1 | 23–29 Nov 2026 | Basics: const, arrays, references, memory, pointers |
| 2 | 30 Nov–6 Dec | Value categories, move, smart pointers, copy |
| 3 | 7–13 Dec | Rule of 3/5, operators, RAII, exceptions |
| 4 | 14–20 Dec | Exceptions and RAII, functors, lambdas |
| 5 | 21–27 Dec | Concurrency |
| 6 | 28 Dec–3 Jan 2027 | Inheritance, virtual functions, vtable |
| 7 | 4–10 Jan | Layout, pImpl, static, templates |
| 8 | 11–17 Jan | SFINAE, perfect forwarding, unions, bits |
| 9 | 18–24 Jan | constexpr, auto, casts |
| 10 | 25–31 Jan | NULL, inlining, strings, vector |
| 11 | 1–7 Feb | list, deque, set, map |
| 12 | 8–14 Feb | unordered_map, container adaptors |
| 13 | 15–21 Feb | Iterators, algorithms |
| 14 | 22–28 Feb | Sorting, binary search, heaps, thread pool |
| 15 | 1–7 Mar | Catch-up |
| 16 | 8–14 Mar | Design questions and project stories |
| 17 | 15–21 Mar | Mock interviews |

Started a day early, on 22 Nov 2026. The dates are targets: the plan follows what is actually finished.

## Sources

- Mike Shah: "The C++ Programming Language" and "Modern C++ (cpp) Concurrency" playlists (main C++ track)
- The Cherno: "C++" playlist (a few topics and code-alongs)
- CodeVault: "Unix Processes in C" and "Unix Threads in C"
- Chris Greer: "How TCP Works"; Jacob Sorber: socket programming videos
- LiveOverflow: "Binary Exploitation / Memory Corruption"; Computerphile: security and TLS videos
- LeetCode problems in C++, with help from Striver's A2Z DSA course, NeetCode 150 and Abdul Bari

The lessons are my own study notes; the videos belong to their creators.
