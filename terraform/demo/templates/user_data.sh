#!/bin/bash
# ============================================================================
# Host provisioning for the demo environment (C17).
#
# FOUR STEPS, AND NOTHING ABOUT THE APPLICATION. No reverse proxy
# configuration, no hostname, no certificate handling, no application
# environment variable, and no enumeration of the individual services. All of
# that lives in `compose.demo.yaml`, in the images, and in the parameter store.
#
# That is what makes this module portable to any account, and it is a
# deliberate departure from the shop's production provisioning, which installs
# and configures nginx, writes a certificate client's cron entry, writes the
# deployment script into the host with a heredoc, and hard-codes seven
# application variables — none of which can be changed without replacing the
# instance, because that module ignores changes to this file.
#
# Runs once, as root, on first boot. Its output lands in
# /var/log/cloud-init-output.log.
# ============================================================================

# Tracing is on HERE and only here: this script reads no secret, and a first
# boot that fails is otherwise very hard to diagnose. It does not propagate to
# `deploy.sh`, which runs as its own shell, without tracing, because it does
# read secrets — do not export SHELLOPTS from this file.
set -euxo pipefail

DEPLOY_ROOT=/opt/jbg-demo
COMPOSE_PLUGIN_DIR=/usr/libexec/docker/cli-plugins

# ─── 1. Container engine and Compose plugin ─────────────────────────────────
#
# The plugin is fetched from a release pinned by the module rather than from a
# moving tag, so the same commit provisions the same host on any day. Amazon
# Linux does not package it.
dnf update -y
dnf install -y docker tar gzip

mkdir -p "$COMPOSE_PLUGIN_DIR"
curl -fsSL \
  "https://github.com/docker/compose/releases/download/${compose_plugin_version}/docker-compose-linux-x86_64" \
  -o "$COMPOSE_PLUGIN_DIR/docker-compose"
chmod +x "$COMPOSE_PLUGIN_DIR/docker-compose"

# ─── 2. System services ─────────────────────────────────────────────────────
#
# The systems management agent ships enabled on this image, but it is asserted
# here anyway: without it the host never registers, and every deployment times
# out waiting for a command nobody can deliver.
systemctl enable --now docker
systemctl enable --now amazon-ssm-agent

# ─── 3. Deployment bundle ───────────────────────────────────────────────────
#
# The composition file and the deployment script, straight from the repository.
# The archive's layout is preserved rather than flattened: the composition file
# mounts `./deploy/demo/Caddyfile` relative to itself.
mkdir -p "$DEPLOY_ROOT"
curl -fsSL "${bundle_url}" -o /tmp/jbg-demo-bundle.tar.gz
tar -xzf /tmp/jbg-demo-bundle.tar.gz -C "$DEPLOY_ROOT" --strip-components=1
rm -f /tmp/jbg-demo-bundle.tar.gz
chmod +x "$DEPLOY_ROOT/deploy/demo/deploy.sh"

# ─── 4. Deploy ──────────────────────────────────────────────────────────────
#
# With no argument, the script deploys the tag recorded in the parameter store.
# On a brand new account that is the placeholder and no image exists yet, so
# this legitimately fails and the first real deployment comes from the
# pipeline. `|| true` keeps a first boot from being reported as a failed one
# for that expected reason; every later boot redeploys the last tag.
"$DEPLOY_ROOT/deploy/demo/deploy.sh" || true
