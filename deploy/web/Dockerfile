# syntax=docker/dockerfile:1
#
# The built browser app behind nginx, which also proxies /api to requirement
# work and /knowledge-api and /knowledge to the knowledge service (ADR-0099).
# Build from the repository root: docker build -f deploy/web/Dockerfile .
# CSP_IDENTITY_ORIGINS must name the OIDC issuer origin for an OIDC deployment;
# it is baked into the page's Content-Security-Policy at build time.

# Matches the Node version CI builds and tests with.
FROM node:24-alpine@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1 AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_API_BASE=/api
# Where the knowledge portal is (ADR-0104): the platform path by default, an
# absolute URL when it has its own host, or empty to hide every link to it.
ARG VITE_KNOWLEDGE_PORTAL_URL=/knowledge/
# Who sees those links: holders of this role, or everyone signed in when empty.
ARG VITE_KNOWLEDGE_PORTAL_ROLE=knowledge_admin
ARG CSP_IDENTITY_ORIGINS=
ENV VITE_API_BASE=$VITE_API_BASE \
    VITE_KNOWLEDGE_PORTAL_URL=$VITE_KNOWLEDGE_PORTAL_URL \
    VITE_KNOWLEDGE_PORTAL_ROLE=$VITE_KNOWLEDGE_PORTAL_ROLE \
    CSP_IDENTITY_ORIGINS=$CSP_IDENTITY_ORIGINS
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.31-alpine@sha256:26b0bf6fbf07297983cb341998d79c831508787de26627dd2a112321b9c3a4af
# Alpine security fixes land between base-image releases; take them at build
# time so the Trivy gate in CI is not waiting on upstream. Then drop back to
# the image's unprivileged user.
USER root
RUN apk upgrade --no-cache
USER 101
# The image renders templates with the environment at start-up (the *_UPSTREAM
# variables below; nginx's own $variables are left alone).
COPY deploy/web/default.conf.template /etc/nginx/templates/default.conf.template
COPY deploy/web/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
COPY deploy/web/knowledge-unavailable.html /usr/share/nginx/html/knowledge-unavailable.html
ENV API_UPSTREAM=http://api:8000 \
    KNOWLEDGE_API_UPSTREAM=http://knowledge-api:8000 \
    KNOWLEDGE_WEB_UPSTREAM=http://knowledge-web:8080
EXPOSE 8080
