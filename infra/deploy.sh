#!/usr/bin/env bash
# Build (local, not container) and deploy the `arrearo` stack. Sends stay in dry mode
# unless you pass SendMode=live:   ./deploy.sh SendMode=live
set -euo pipefail
cd "$(dirname "$0")"
export AWS_PROFILE="${AWS_PROFILE:-default}" AWS_DEFAULT_REGION=us-east-1
SAM="${SAM:-$(command -v sam || echo ../.venv/bin/sam)}"
export PATH="$(cd .. && pwd)/.venv/bin:$PATH"       # python3.12 for the local build

"$SAM" build
if [ "$#" -gt 0 ]; then
  "$SAM" deploy --no-confirm-changeset --no-fail-on-empty-changeset --parameter-overrides "$@"
else
  "$SAM" deploy --no-confirm-changeset --no-fail-on-empty-changeset
fi
aws cloudformation describe-stacks --stack-name arrearo --region us-east-1 \
  --query 'Stacks[0].Outputs[].[OutputKey,OutputValue]' --output table
