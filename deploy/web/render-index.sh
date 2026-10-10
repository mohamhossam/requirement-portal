#!/bin/sh
# Renders this deployment's values into the app's index.html when the container
# starts, so one web image serves every deployment (production hardening PR 12).
# nginx serves the result from the /run/web tmpfs; the image's own copy keeps its
# placeholders.
#
#   CSP_IDENTITY_ORIGINS   the OIDC issuer origins, space-separated, for the page's
#                          Content-Security-Policy. Required unless IDENTITY_PROVIDER=fake:
#                          without them the browser refuses to talk to the issuer.
#   KNOWLEDGE_PORTAL_URL   where the knowledge portal is, ending in /, or empty to hide
#                          every link to it (10-check-knowledge-portal-url.sh checks it too).
#   KNOWLEDGE_PORTAL_ROLE  who sees those links: holders of this role, or everyone signed
#                          in when empty.
set -eu
# The origins are split on spaces below; never expand them as file patterns.
set -f

source_html="${RENDER_INDEX_SOURCE:-/usr/share/nginx/html/index.html}"
target_html="${RENDER_INDEX_TARGET:-/run/web/index.html}"
identity_provider="${IDENTITY_PROVIDER:-oidc}"
portal_url="${KNOWLEDGE_PORTAL_URL:-}"
portal_role="${KNOWLEDGE_PORTAL_ROLE-knowledge_admin}"

refuse() {
  echo "$1" >&2
  exit 1
}

# Each value lands in an HTML attribute and a sed replacement, so only the characters
# an origin, URL or role needs are allowed: no quotes, spaces, newlines, |, & or
# backslashes. Each check lists what is allowed, so anything else is refused.
origins=""
for origin in ${CSP_IDENTITY_ORIGINS:-}; do
  host="${origin#http://}"
  host="${host#https://}"
  host="${host%/}"
  case "$origin" in
    http://* | https://*) ;;
    *) refuse "CSP_IDENTITY_ORIGINS must list http(s) origins without a path: $origin" ;;
  esac
  case "$host" in
    "" | *[!A-Za-z0-9.:-]*)
      refuse "CSP_IDENTITY_ORIGINS must list http(s) origins without a path: $origin" ;;
  esac
  origins="$origins ${origin%/}"
done
if [ "$identity_provider" != fake ] && [ -z "$origins" ]; then
  refuse "CSP_IDENTITY_ORIGINS must name the OIDC issuer origin; without it the browser cannot sign in."
fi
case "$portal_url" in
  "") ;;
  *[!A-Za-z0-9._~:/@%+-]*) refuse "KNOWLEDGE_PORTAL_URL must be an http(s) URL ending in /, or empty: $portal_url" ;;
  http://?*/ | https://?*/) ;;
  *) refuse "KNOWLEDGE_PORTAL_URL must be an http(s) URL ending in /, or empty: $portal_url" ;;
esac
case "$portal_role" in
  *[!A-Za-z0-9_.-]*) refuse "KNOWLEDGE_PORTAL_ROLE may hold only letters, digits, '.', '_' and '-': $portal_role" ;;
esac

# The origins placeholder always follows a space (contentSecurityPolicy.ts), so an
# empty list leaves no stray space behind.
sed \
  -e "s| __CSP_IDENTITY_ORIGINS__|$origins|g" \
  -e "s|__KNOWLEDGE_PORTAL_URL__|$portal_url|g" \
  -e "s|__KNOWLEDGE_PORTAL_ROLE__|$portal_role|g" \
  "$source_html" > "$target_html.tmp"
if grep -q '__CSP_IDENTITY_ORIGINS__\|__KNOWLEDGE_PORTAL_URL__\|__KNOWLEDGE_PORTAL_ROLE__' "$target_html.tmp"; then
  refuse "$source_html has a placeholder this script does not fill."
fi
mv "$target_html.tmp" "$target_html"
