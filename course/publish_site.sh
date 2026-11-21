#!/usr/bin/env bash
# Publish the generated website (course/site/) to the separate PUBLIC repo that serves GitHub Pages,
# so this repo (source, notes, tests) can stay private.
#
#   cd study-roadmap && python3 gen_study.py       # build first
#   ./publish_site.sh [path-to-clone-of-the-public-repo]     (default: ../../cpp-linux-interview-course)
#
# By default the new site is pushed to a feature branch (publish/<source-commit>-<time>) and the script prints the
# link to open a pull request; merging that PR into main is what makes it live. Nothing reaches main unreviewed.
#   DIRECT=1 ./publish_site.sh ...                 # push straight to main (also used automatically for the very
#                                                  # first publish into an empty repo, which has no main yet)
#   DRY_RUN=1 ./publish_site.sh ...                # copy and commit locally, don't push
#   SITE_REPO=other-name ./publish_site.sh ...     # if the public repo is not called cpp-linux-interview-course
#
# The target must be a git clone of the public repo (its remote URL has to contain its name, "cpp-linux-interview-course" by
# default); the script refuses anything else, because it REPLACES the contents of that clone with site/
# (only .git and the repo's README.md are kept).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
site="$here/site"
name="${SITE_REPO:-cpp-linux-interview-course}"
target="${1:-$here/../../$name}"

[ -f "$site/index.html" ] || { echo "No $site/index.html: run 'python3 gen_study.py' first." >&2; exit 1; }
[ -d "$target/.git" ] || { echo "$target is not a git clone of the public repo." >&2; exit 1; }
target="$(cd "$target" && pwd)"
url="$(git -C "$target" remote get-url origin 2>/dev/null || true)"
case "$url" in *"$name"*) ;; *) echo "Refusing: origin of $target is '$url', not the $name repo." >&2; exit 1;; esac

# start from the public repo's current main, so the new branch contains only this publish
if git -C "$target" ls-remote --exit-code --heads origin main >/dev/null 2>&1; then
  git -C "$target" fetch -q origin main
  git -C "$target" checkout -q -B main origin/main
  first=0
else
  first=1                                   # empty repo: there is no main to branch from yet
fi

# replace everything except .git and the repo's own README.md with the fresh site
find "$target" -mindepth 1 -maxdepth 1 ! -name .git ! -name README.md -exec rm -rf {} +
cp -a "$site"/. "$target"/
touch "$target/.nojekyll"        # serve files as-is, no Jekyll processing

cd "$target"
src="$(git -C "$here" rev-parse --short HEAD 2>/dev/null || echo unknown)"
direct=0; { [ "${DIRECT:-}" = 1 ] || [ "$first" = 1 ]; } && direct=1
branch="main"
if [ "$direct" = 0 ]; then branch="publish/$src-$(date +%Y%m%d-%H%M%S)"; git checkout -q -b "$branch"; fi

# rebuild the index from file CONTENTS: cp -a keeps source timestamps, and git's stat shortcut could otherwise miss a
# changed file of the same size (e.g. a new ?v=<hash> in every page)
git read-tree --empty
git add -A
if git diff --cached --quiet; then
  echo "Nothing changed: the public site is already up to date."
  [ "$direct" = 0 ] && { git checkout -q main; git branch -q -D "$branch"; }
  exit 0
fi
git commit -q -m "Publish site (built from source commit $src)"
if [ "${DRY_RUN:-}" = 1 ]; then echo "DRY_RUN: committed locally ($( [ "$direct" = 1 ] && echo "would go to main" || echo "would push branch $branch")), not pushed."; exit 0; fi
if [ "$direct" = 1 ]; then
  git push -q origin HEAD:refs/heads/main        # whatever the local branch is called, publish to main
  echo "Pushed straight to main. Pages updates in a minute or two."
else
  git push -q origin "$branch"
  git checkout -q main && git branch -q -D "$branch"      # the branch lives on the remote; keep the clone on main
  repo_url="${url%.git}"
  echo "Pushed branch '$branch'. Open a pull request to publish it:"
  echo "  $repo_url/compare/main...${branch}?expand=1"
  echo "Merging it into main makes the new site live (Pages updates in a minute or two)."
fi
