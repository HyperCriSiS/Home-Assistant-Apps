FROM docker.io/hiett/serverless-redis-http:0.0.10@sha256:65128347949bca511e448fd7238780d624573d74c22b79155a7563db19e9b678 AS redis_http

# Inbox Zero built from the pinned fork commit by build-inbox-zero-base.yml.
FROM ghcr.io/hypercrisis/inbox-zero-base:a08ec63f0c09739e49385134d6a17a176be43683

ARG BUILD_VERSION
ARG BUILD_ARCH

LABEL \
    io.hass.name="Inbox Zero" \
    io.hass.description="AI email assistant with bundled PostgreSQL and Redis" \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="app" \
    io.hass.arch="${BUILD_ARCH}" \
    org.opencontainers.image.source="https://github.com/HyperCriSiS/Home-Assistant-Apps" \
    org.opencontainers.image.version="${BUILD_VERSION}"

# PostgreSQL 16 matches the upstream Compose setup; the major version is part
# of the package name so a base image update can never change it silently.
# libstdc++ and ncurses are runtime libraries of the Redis HTTP adapter.
# hadolint ignore=DL3018
RUN apk add --no-cache \
        bash curl jq su-exec \
        postgresql16 postgresql16-contrib \
        redis \
        libstdc++ ncurses-libs

COPY --from=redis_http /app/_build/prod/rel/prod /opt/redis-http
COPY run.sh cron.sh /usr/local/bin/
RUN chmod 0755 /usr/local/bin/run.sh /usr/local/bin/cron.sh

CMD ["/usr/local/bin/run.sh"]
