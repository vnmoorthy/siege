#!/usr/bin/env bash
# Publish the war room in in-browser mock mode to GitHub Pages (https://vnmoorthy.github.io/siege/).
# Mock mode is a self-contained simulator: no backend, no keys, clearly labeled MOCK DATA in the UI.
set -euo pipefail
cd "$(dirname "$0")/.."
( cd frontend && VITE_MOCK=1 npx vite build --base=/siege/ --outDir dist-pages --emptyOutDir )
cp frontend/dist-pages/index.html frontend/dist-pages/404.html   # SPA fallback for /attack and /admin
touch frontend/dist-pages/.nojekyll
rm -rf /tmp/siege-pages && git worktree prune && git worktree add -B gh-pages /tmp/siege-pages 2>/dev/null || git worktree add /tmp/siege-pages gh-pages
rsync -a --delete --exclude .git frontend/dist-pages/ /tmp/siege-pages/
( cd /tmp/siege-pages && git add -A && git -c user.name=vnmoorthy -c user.email=182589719+vnmoorthy@users.noreply.github.com commit -qm "deploy pages" || true; git push -f origin gh-pages )
git worktree remove --force /tmp/siege-pages
echo "pushed gh-pages; enable Pages: gh api -X POST repos/vnmoorthy/siege/pages -f source[branch]=gh-pages -f source[path]=/"
