#!/usr/bin/env bash
# Commits and pushes the working tree every INTERVAL seconds while files change. Used during the hackathon build.
INTERVAL=${1:-120}
cd "$(dirname "$0")/.."
while true; do
  if [ -n "$(git status --porcelain)" ]; then
    N=$(git status --porcelain | wc -l | tr -d ' ')
    FILES=$(git status --porcelain | awk '{print $2}' | head -3 | tr '\n' ' ')
    git add -A >/dev/null 2>&1
    git -c user.name=vnmoorthy -c user.email=182589719+vnmoorthy@users.noreply.github.com commit -qm "wip $(date +%H:%M): ${N} paths changed (${FILES}...)" && git push -q origin main 2>>/tmp/siege_autocommit.log && echo "$(date +%H:%M:%S) committed ${N} paths" >> /tmp/siege_autocommit.log
  fi
  sleep "$INTERVAL"
done
