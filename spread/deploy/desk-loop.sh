#!/bin/bash
# The loop that played the final of 15 Nov 2026 on the runner in Helsinki, in tmux session "final":
# trackb-merge-8.3 (2942593c, --variant m41u-b-bud-b-x720-819), without the note watcher, as it was replayed.
# Installed as ~/.config/spread/desk-loop (mode 700); the team key and the note model's settings sit beside it (mode 600).
# Start: tmux new-session -d -s final ~/.config/spread/desk-loop
export SPREAD_KEY="$(cat ~/.config/spread/key)"
set -a; . ~/.config/spread/note-model.env; set +a
cd ~/code/junction2026/final/spread
while true; do ~/.local/bin/uv run python -m spreadlab.live final --variant m41u-b-bud-b-x720-819; sleep 3; done
