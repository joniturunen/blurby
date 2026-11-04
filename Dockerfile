# Two stages: the first installs Blurby and its dependencies into /opt/venv
# with uv; the image itself gets only that virtualenv, without uv or the
# build files.
FROM python:3.14-alpine3.24 AS build

# Install a pinned uv binary from its official image
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /bin/uv

# Install into /opt/venv with the base image's own Python, which the second
# stage has at the same path.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

WORKDIR /build

# Install the locked dependencies before copying the app so this layer is
# cached across code changes
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# Install the blurby package itself (non-editable, so /opt/venv is self-contained)
COPY src ./src
RUN uv sync --locked --no-dev --no-editable


FROM python:3.14-alpine3.24

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

ENV PATH="/opt/venv/bin:$PATH"

# Blurby doesn't need pip, which the base image brings along with its own
# dependencies. The non-root user has an explicit UID: a mounted data folder
# must be writable by UID 5678. It owns only the data folder.
RUN python -m pip uninstall --yes --root-user-action ignore pip \
    && addgroup -g 5678 appuser \
    && adduser -u 5678 -G appuser -D -g "" appuser \
    && mkdir -p /blurby/data \
    && chown appuser:appuser /blurby/data

# The virtualenv stays root-owned, so Blurby can't change its own code.
COPY --from=build /opt/venv /opt/venv

# /blurby is the runtime directory; the database lives in /blurby/data.
# Blurby logs to stdout (`docker logs`), so there is no log volume.
WORKDIR /blurby
VOLUME /blurby/data/

# Numeric, so that Kubernetes' runAsNonRoot can check it
USER 5678

CMD ["blurby"]
