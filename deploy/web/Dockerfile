# syntax=docker/dockerfile:1
#
# The built browser app behind nginx, which also proxies /api to requirement
# work. The knowledge portal has its own address (ADR-0104).
# Build from the repository root: docker build -f deploy/web/Dockerfile .
# One image serves every deployment: its issuer origins and knowledge-portal
# link are set when the container starts (render-index.sh), not at build time.

# Matches the Node version CI builds and tests with.
FROM node:24-alpine@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1 AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_API_BASE=/api
# Placeholders for the deployment's values, which render-index.sh fills in.
ENV VITE_API_BASE=$VITE_API_BASE \
    WEB_RUNTIME_CONFIG=true
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.31-alpine@sha256:26b0bf6fbf07297983cb341998d79c831508787de26627dd2a112321b9c3a4af
# Alpine security fixes land between base-image releases; take them at build
# time so the Trivy gate in CI is not waiting on upstream. Then drop back to
# the image's unprivileged user.
USER root
RUN apk upgrade --no-cache
USER 101
# The image renders templates with the environment at start-up (API_UPSTREAM
# and KNOWLEDGE_PORTAL_URL below; nginx's own $variables are left alone).
COPY deploy/web/default.conf.template /etc/nginx/templates/default.conf.template
COPY deploy/web/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --chmod=755 deploy/web/check-knowledge-portal-url.sh /docker-entrypoint.d/10-check-knowledge-portal-url.sh
COPY --chmod=755 deploy/web/render-index.sh /docker-entrypoint.d/30-render-index.sh
COPY --from=build /app/dist /usr/share/nginx/html
# Set when the container starts:
# CSP_IDENTITY_ORIGINS: the OIDC issuer origins the page may talk to; required
# unless IDENTITY_PROVIDER=fake (render-index.sh refuses to start otherwise).
# KNOWLEDGE_PORTAL_URL: the knowledge portal, ending in /, for the app's links and
# old /knowledge/ bookmarks; empty hides the links and answers bookmarks 404.
# KNOWLEDGE_PORTAL_ROLE: who sees those links; empty means everyone signed in.
# TRUSTED_PROXY_CIDR: the TLS proxy in front, allowed to name the client address
# (the default trusts no one). EDGE_RATE_PER_SECOND and EDGE_BURST: each client
# address's API budget at this edge (ADR-0106).
ENV API_UPSTREAM=http://api:8000 \
    IDENTITY_PROVIDER=oidc \
    CSP_IDENTITY_ORIGINS= \
    KNOWLEDGE_PORTAL_URL= \
    KNOWLEDGE_PORTAL_ROLE=knowledge_admin \
    TRUSTED_PROXY_CIDR=127.0.0.1/32 \
    EDGE_RATE_PER_SECOND=50 \
    EDGE_BURST=100
EXPOSE 8080
