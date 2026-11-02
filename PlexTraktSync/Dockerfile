ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian:bookworm
FROM ${BUILD_FROM}
ARG PTS_VERSION=0.35.21
ARG PTS_SHA256=ad4d319f89c92a05150dcb6ac3d88c5cf9f8aa106444ff48d7e4bf2346e7ad0e
ARG BUILD_VERSION
ARG BUILD_ARCH
LABEL io.hass.type="app" io.hass.version="${BUILD_VERSION}" io.hass.arch="${BUILD_ARCH}" \
      org.opencontainers.image.source="https://github.com/HyperCriSiS/Home-Assistant-Apps"
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3 python3-venv ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/pts \
    && /opt/pts/bin/pip download --no-cache-dir --no-deps "PlexTraktSync==${PTS_VERSION}" -d /tmp/pts \
    && echo "${PTS_SHA256}  /tmp/pts/plextraktsync-${PTS_VERSION}-py3-none-any.whl" | sha256sum -c - \
    && /opt/pts/bin/pip install --no-cache-dir /tmp/pts/*.whl \
    && rm -rf /tmp/pts \
    && useradd --uid 1000 --no-create-home --shell /usr/sbin/nologin pts
COPY app /app
COPY default-options.json /app/default-options.json
COPY run.sh /run.sh
RUN chmod 755 /run.sh
ENV PATH="/opt/pts/bin:${PATH}" HOME=/data PTS_CONFIG_DIR=/data/pts \
    PTS_CACHE_DIR=/data/cache PTS_LOG_DIR=/data/log PYTHONUNBUFFERED=1
WORKDIR /app
ENTRYPOINT ["/run.sh"]
