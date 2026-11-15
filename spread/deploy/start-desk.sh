#!/bin/bash
# Starts the Spread desk on this standby, in tmux session "final": the same loop as on the first machine.
# First make sure that the first desk cannot come back: its tmux session killed, or its instance stopped.
# Installed as ~/bin/start-desk on the standby. Usage: start-desk [live final options], for example:
#   start-desk --variant m41u-b-bud-b-x720-819
set -eu
cd ~/code/junction2026/spread
if tmux has-session -t final 2>/dev/null; then
  echo "A desk already runs here: tmux attach -t final"
  exit 1
fi
cat > ~/.config/spread/desk-loop <<EOF
#!/bin/bash
export SPREAD_KEY=\$(cat ~/.config/spread/key)
set -a; . ~/.config/spread/note-model.env; set +a
while true; do ~/.local/bin/uv run python -m spreadlab.live final $*; sleep 3; done
EOF
chmod 700 ~/.config/spread/desk-loop
tmux new-session -d -s final -c ~/code/junction2026/spread ~/.config/spread/desk-loop
echo "Started at $(date -u +%H:%M:%S) UTC. Watch it: tmux attach -t final"
