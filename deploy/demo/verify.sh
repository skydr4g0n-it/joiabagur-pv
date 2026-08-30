#!/usr/bin/env bash
# ============================================================================
# verify.sh — post-deployment verification for the demo environment (C17)
#
# RUNS INSIDE THE HOST, invoked through the systems management service by
# `.github/workflows/deploy-demo.yml`.
#
# It runs here and not on the pipeline runner because the AI service is PRIVATE
# BY DESIGN: it publishes no port, and the security group opens only the two the
# reverse proxy serves. A runner outside the environment cannot reach it, and
# making it reachable so that it could be checked would destroy precisely the
# property the check exists to protect (C17 D21).
#
# It fails the deployment on any of four conditions, and the first one is the
# reason this script exists at all:
#
#   1. Zero indexed documents. A deployment with an empty index answers 200s,
#      serves a valid certificate, and finds nothing. It looks like success.
#   2. The configured embedding model disagrees with the one recorded on the
#      index rows: queries and documents would live in two different vector
#      spaces, producing noise with no error anywhere.
#   3. The database is unreachable.
#   4. The embedding provider credential is not configured.
#
# Note what it does NOT do: it never asks whether the provider is answering.
# `/health` does not call it either. A third-party outage is not a failed
# deployment.
# ============================================================================

set -euo pipefail

# Plain `docker exec` on the container name, NOT `docker compose exec`. Compose
# would parse the composition file to resolve the service, and parsing it means
# interpolating every `${VAR}` in it — none of which are exported when this runs
# on its own. The result is a screen of "variable is not set" warnings on a
# verification that is working perfectly, which is exactly the kind of noise that
# teaches people to ignore output. The name is fixed by `container_name:`.
AI_CONTAINER="jbg-demo-ai"

echo "[verify] Probing the AI service health report from inside the host ..."

docker exec -i "${AI_CONTAINER}" python - <<'PYTHON'
import json
import sys
import urllib.request

with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=10) as response:
    body = json.load(response)

print(json.dumps(body, indent=2, sort_keys=True))

index = body.get("index") or {}
failures = []

if body.get("database") != "ok":
    failures.append(f"database is {body.get('database')!r}, expected 'ok'")

documents = index.get("documents")
if not isinstance(documents, int) or documents <= 0:
    failures.append(
        f"indexed documents is {documents!r}; an environment with an empty index "
        "answers every request successfully and finds nothing"
    )

if index.get("status") != "ok":
    failures.append(
        f"index status is {index.get('status')!r} (configured model "
        f"{index.get('configured_model')!r} vs indexed {index.get('model')!r})"
    )

if body.get("provider") != "configured":
    failures.append(f"provider credential is {body.get('provider')!r}, expected 'configured'")

if failures:
    print("[verify] FAILED:", file=sys.stderr)
    for failure in failures:
        print(f"  - {failure}", file=sys.stderr)
    sys.exit(1)

print(f"[verify] OK — {documents} documents indexed with {index.get('model')}")
PYTHON

echo "[verify] Post-deployment verification passed."
