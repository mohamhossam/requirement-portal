#!/bin/sh
# Runs before nginx renders its templates. Old /knowledge/ bookmarks are
# redirected to KNOWLEDGE_PORTAL_URL with their path appended, so it must be an
# http(s) URL ending in /, or empty (ADR-0104).
case "${KNOWLEDGE_PORTAL_URL:-}" in
  "" | http://*/ | https://*/) ;;
  *)
    echo "KNOWLEDGE_PORTAL_URL must be an http(s) URL ending in /, or empty: ${KNOWLEDGE_PORTAL_URL}" >&2
    exit 1
    ;;
esac
