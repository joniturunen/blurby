# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3.14-slim-trixie

# Install a pinned uv binary from its official image
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /bin/uv

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Install dependencies into /opt/venv using the image's own Python. The
# virtualenv lives outside /blurby so it stays root-owned and out of the volumes.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build

# Install the locked dependencies before copying the app so this layer is
# cached across code changes
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# Install the blurby package itself (non-editable, so /opt/venv is self-contained)
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

# /blurby is the runtime directory; the default database lives in /blurby/data.
# Blurby logs to stdout (`docker logs`), so there is no log volume.
WORKDIR /blurby
RUN mkdir -p /blurby/data

# Define volumes
VOLUME /blurby/data/

# Creates a non-root user with an explicit UID and adds permission to access the /blurby folder
# For more info, please refer to https://aka.ms/vscode-docker-python-configure-containers
RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /blurby

# Add permissions to /data for user appuser
RUN chown -R appuser /blurby/data
USER appuser

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
CMD ["blurby"]
