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
# It fails the deployment on any of five conditions, and the first one is the
# reason this script exists at all:
#
#   1. Zero indexed documents. A deployment with an empty index answers 200s,
#      serves a valid certificate, and finds nothing. It looks like success.
#   2. The configured embedding model disagrees with the one recorded on the
#      index rows: queries and documents would live in two different vector
#      spaces, producing noise with no error anywhere.
#   3. The database is unreachable.
#   4. The embedding provider credential is not configured.
#   5. The point-of-sale availability projection holds no assigned row for some
#      point of sale (C41). Same shape as the first, one table along: every
#      scoped retrieval answers 503, the API degrades correctly to its lexical
#      path with a 200, and the environment looks healthy from outside. It had
#      already reached this environment once, in C34.
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

# Fifth condition (C41), and the same shape as the first one table along. An environment whose
# index is full but whose point-of-sale projection is empty PASSED this check until now: every
# scoped retrieval answers 503, the .NET side degrades correctly to its lexical path and answers
# 200, a valid certificate is served and the screens render — so the deployment looks like a
# success and quietly finds nothing that the assortment should have narrowed. It reached a
# deployed environment once already, and the deferred task recording it is closed by this block.
#
# Tolerant of an older AI image that does not report the section: absent is not a failure, it is
# a version skew, and failing a deployment for it would be a false alarm about the wrong thing.
projection = body.get("projection")
if isinstance(projection, dict):
    points_of_sale = projection.get("points_of_sale")
    without_scope = projection.get("shops_without_scope")

    if projection.get("status") == "never_drained":
        failures.append(
            "the point-of-sale projection has never been drained; every scoped retrieval "
            "will answer 503 while this deployment looks healthy from outside"
        )
    elif isinstance(points_of_sale, int) and points_of_sale == 0:
        failures.append(
            "the point-of-sale projection holds no rows at all; assisted search cannot be "
            "scoped to any shop"
        )
    elif isinstance(without_scope, int) and without_scope > 0:
        failures.append(
            f"{without_scope} point(s) of sale hold no assigned row in the projection; "
            "assisted search answers 503 for each of them"
        )

if failures:
    print("[verify] FAILED:", file=sys.stderr)
    for failure in failures:
        print(f"  - {failure}", file=sys.stderr)
    sys.exit(1)

print(f"[verify] OK — {documents} documents indexed with {index.get('model')}")
if isinstance(projection, dict):
    print(
        f"[verify] OK — projection drained {projection.get('age_seconds')}s ago, "
        f"{projection.get('points_of_sale')} point(s) of sale scoped"
    )
PYTHON

echo "[verify] Post-deployment verification passed."
