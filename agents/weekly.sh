#!/usr/bin/env bash
# Multi-agent orchestration as CLI composition: each agent is a command, composed in sequence.
# The risk agent runs last so it can read the drafts produced by the other two.
# Usage: bash weekly.sh [--offline] [--today YYYY-MM-DD] [--model MODEL]
set -euo pipefail
cd "$(dirname "$0")"
for agent in tracker budget risk_adr; do
  python3 -m pm_agents "$agent" "$@"
  echo
done
echo "Next step: python3 -m pm_agents review"
