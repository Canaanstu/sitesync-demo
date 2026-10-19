#!/usr/bin/env bash
# Deploy the backend then the frontend to Vercel production. Run from anywhere:  bash deploy/deploy-vercel.sh
# One-time setup on a new machine:  npx vercel@latest login   (then the folders are already linked via .vercel/)
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
for dir in backend frontend; do
  echo "==> Deploying $dir"
  (cd "$root/$dir" && npx --yes vercel@latest deploy --prod --yes)
done
echo "Done: https://sitesync-demo.vercel.app"
