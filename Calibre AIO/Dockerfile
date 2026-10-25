ARG BUILD_FROM
ARG CWA_VERSION
ARG CALIBRE_RELEASE
ARG KEPUBIFY_RELEASE

# ==============================================================================
# Stage 1: Fetch and build Calibre-Web Automated (source), its Python
# dependencies, kepubify and Calibre itself. Upstream distributes these as
# part of a single ghcr.io/linuxserver/baseimage-ubuntu image; here they are
# fetched from their original upstream sources instead, so the add-on can be
# built directly on the official Home Assistant base image rather than a
# third-party one.
# ==============================================================================
FROM ${BUILD_FROM} AS build

ARG CWA_VERSION
ARG CWA_REF
ARG CWA_SHA256
ARG CALIBRE_RELEASE
ARG KEPUBIFY_RELEASE

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        xz-utils \
        gettext \
        build-essential \
        python3 \
        python3-dev \
        python3-venv \
        libldap2-dev \
        libsasl2-dev \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 911 abc \
    && useradd -u 911 -g abc -M -s /usr/sbin/nologin abc

# Fetch the Calibre-Web Automated source tree for the pinned release tag
RUN mkdir -p /app/calibre-web-automated \
    && curl -fsSL "https://github.com/crocodilestick/Calibre-Web-Automated/archive/${CWA_REF}.tar.gz" -o /tmp/cwa.tar.gz \
    && echo "${CWA_SHA256}  /tmp/cwa.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/cwa.tar.gz --strip-components=1 -C /app/calibre-web-automated \
    && rm /tmp/cwa.tar.gz \
    && bash /app/calibre-web-automated/scripts/compile_translations.sh

# Build the Python virtual environment used to run CWA
RUN python3 -m venv /opt/cwa-venv \
    && /opt/cwa-venv/bin/pip install --no-cache-dir -U pip wheel \
    && /opt/cwa-venv/bin/pip install --no-cache-dir \
        -r /app/calibre-web-automated/requirements.txt \
        -r /app/calibre-web-automated/optional-requirements.txt

# kepubify: static binary release, converts EPUB to KEPUB for Kobo devices
RUN set -eu; \
    case "$(uname -m)" in \
        x86_64)  kbin=kepubify-linux-64bit ;; \
        aarch64) kbin=kepubify-linux-arm64 ;; \
        *) echo "Unsupported architecture: $(uname -m)" >&2; exit 1 ;; \
    esac; \
    curl -fsSL -o /usr/bin/kepubify \
        "https://github.com/pgaskin/kepubify/releases/download/${KEPUBIFY_RELEASE}/${kbin}" \
    && chmod +x /usr/bin/kepubify

# Calibre: official self-contained Linux binary release (bundles its own Qt/Python)
RUN set -eu; \
    case "$(uname -m)" in \
        x86_64)  carch=x86_64 ;; \
        aarch64) carch=arm64 ;; \
        *) echo "Unsupported architecture: $(uname -m)" >&2; exit 1 ;; \
    esac; \
    mkdir -p /app/calibre; \
    curl -fsSL "https://download.calibre-ebook.com/${CALIBRE_RELEASE}/calibre-${CALIBRE_RELEASE}-${carch}.txz" \
        | tar -xJ -C /app/calibre

RUN printf '%s' "${CWA_VERSION}" > /app/CWA_RELEASE \
    && printf '%s' "${CALIBRE_RELEASE}" > /CALIBRE_RELEASE

# Validate the upstream service contract before packaging HA-specific topology.
RUN for service in cwa-init cwa-auto-library cwa-auto-zipper cwa-checksum-backfill \
        cwa-ingest-service cwa-process-recovery metadata-change-detector calibre-binaries-setup; do \
        test -f "/app/calibre-web-automated/root/etc/s6-overlay/s6-rc.d/${service}/run" \
        && bash -n "/app/calibre-web-automated/root/etc/s6-overlay/s6-rc.d/${service}/run" || exit 1; \
    done


FROM ghcr.io/astral-sh/uv:0.12.19@sha256:04d046b13e60d6bcec73cbc5e1cad25d680dea90c8573340950a0ac2d1aef424 AS uv

FROM build AS shelfmark-build
ARG SHELFMARK_REF
ARG SHELFMARK_SHA256
ARG SHELFMARK_PYTHON
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PYTHON_INSTALL_DIR=/opt/shelfmark-python UV_PYTHON_PREFERENCE=only-managed
RUN mkdir -p /app/shelfmark \
    && curl -fsSL "https://github.com/calibrain/shelfmark/archive/${SHELFMARK_REF}.tar.gz" -o /tmp/shelfmark.tar.gz \
    && echo "${SHELFMARK_SHA256}  /tmp/shelfmark.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/shelfmark.tar.gz --strip-components=1 -C /app/shelfmark \
    && rm /tmp/shelfmark.tar.gz \
    && uv python install "${SHELFMARK_PYTHON}"
WORKDIR /app/shelfmark
RUN uv sync --locked --no-default-groups --python "${SHELFMARK_PYTHON}"

FROM node:24-alpine@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1 AS shelfmark-frontend
WORKDIR /frontend
COPY --from=shelfmark-build /app/shelfmark/src/frontend/package*.json ./
RUN npm ci
COPY --from=shelfmark-build /app/shelfmark/src/frontend/ ./
RUN npm run build

FROM ${BUILD_FROM}

ARG CWA_VERSION
ARG BUILD_VERSION

# Labels
LABEL \
    io.hass.name="Calibre AIO" \
    io.hass.description="Shelfmark discovery and Calibre-Web Automated library" \
    io.hass.type="addon" \
    io.hass.version="${BUILD_VERSION}" \
    org.opencontainers.image.source="https://github.com/HyperCriSiS/Home-Assistant-Apps" \
    maintainer="HyperCriSiS"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        imagemagick \
        ghostscript \
        sqlite3 \
        zip \
        inotify-tools \
        xdg-utils \
        curl \
        netcat-openbsd \
        nginx-light \
        libasound2 \
        libffi8 \
        libnss3 \
        libgl1 \
        libegl1 \
        libopengl0 \
        libxi6 \
        libxtst6 \
        libxrandr2 \
        libxkbfile1 \
        libxkbcommon0 \
        libxcomposite1 \
        libxcursor1 \
        libxfixes3 \
        libxrender1 \
        libxdamage1 \
        libxslt1.1 \
        libmagic1 \
        xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Best-effort extras: exact package names/availability can drift between
# Debian releases, and none of these are required for CWA's core web UI to
# come up, so a missing one shouldn't fail the whole build.
#   - unrar-free: lets the ingest folder unpack .cbr comic archives
#   - libglx-mesa0: newer Mesa GLX loader, needed by some Qt6/WebEngine builds
RUN apt-get update \
    && ( apt-get install -y --no-install-recommends unrar-free \
         || echo "unrar-free not available for this base image; .cbr/.rar extraction will not work" ) \
    && ( apt-get install -y --no-install-recommends libglx-mesa0 \
         || echo "libglx-mesa0 not available for this base image; skipping" ) \
    && rm -rf /var/lib/apt/lists/* \
    && if [ ! -e /usr/bin/unrar ] && [ -e /usr/bin/unrar-free ]; then \
         ln -s /usr/bin/unrar-free /usr/bin/unrar; \
       fi

RUN groupadd -g 911 abc \
    && useradd -u 911 -g abc -M -s /usr/sbin/nologin abc

# Copy the built app, its venv, Calibre and kepubify from the build stage
COPY --from=build /app/calibre-web-automated /app/calibre-web-automated
COPY --from=build /app/calibre /app/calibre
COPY --from=build /app/CWA_RELEASE /app/CWA_RELEASE
COPY --from=build /CALIBRE_RELEASE /CALIBRE_RELEASE
COPY --from=build /usr/bin/kepubify /usr/bin/kepubify
COPY --from=build /opt/cwa-venv /opt/cwa-venv
COPY --from=shelfmark-build /app/shelfmark /app/shelfmark
COPY --from=shelfmark-build /opt/shelfmark-python /opt/shelfmark-python
COPY --from=shelfmark-frontend /frontend/dist /app/shelfmark/frontend-dist

# Run bare `python3` (as used throughout CWA's own scripts) against the venv
ENV PATH="/opt/cwa-venv/bin:${PATH}"
ENV CALIBRE_CONFIG_DIR="/config/.config/calibre"

# Copy add-on rootfs (HA-specific cont-init.d bootstrap + CWA's own s6-rc.d services)
COPY rootfs /

# Required directories, ownership and script permissions
RUN mkdir -p \
        /app/calibre-web-automated/metadata_change_logs \
        /app/calibre-web-automated/metadata_temp \
        /app/calibre-web-automated/cps/cache \
    && chown -R abc:abc /app/calibre-web-automated /etc/s6-overlay \
    && chmod a+x /etc/cont-init.d/*.sh \
    && chmod a+x /etc/s6-overlay/s6-rc.d/*/run

WORKDIR /

EXPOSE 8084
