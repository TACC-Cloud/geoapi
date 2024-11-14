FROM python:3.11-slim AS python-base

LABEL maintainer="DesignSafe-CI <designsafe-ci@tacc.utexas.edu>"

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    build-essential \
    software-properties-common \
    libgdal-dev \
    ffmpeg \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# https://python-poetry.org/docs/configuration/#using-environment-variables
ENV POETRY_VERSION=1.8 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=false \
    PYSETUP_PATH="/opt/pysetup" \
    VENV_PATH="/opt/pysetup/.venv"

ENV PATH="$VENV_PATH/bin:$POETRY_HOME/bin:$PATH"

# Install poetry version $POETRY_VERSION to $POETRY_HOME
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel \
    && python3 -m venv "$POETRY_HOME" \
    && "$POETRY_HOME/bin/pip" install --no-cache-dir poetry=="$POETRY_VERSION"

# Copy project requirement files to ensure they will be cached.
WORKDIR $PYSETUP_PATH

COPY devops/poetry.lock devops/pyproject.toml ./

##############
# `development` image target is used for local development
FROM python-base AS development

# Install dev dependencies
RUN "$POETRY_HOME/bin/poetry" install --with dev,flask

COPY geoapi /app/geoapi

WORKDIR /app/geoapi

##############
# `production` image target is used for deployed runtime environments
FROM python-base AS production

# Install runtime dependencies
RUN "$POETRY_HOME/bin/poetry" install --with flask

COPY geoapi /app/geoapi

WORKDIR /app/geoapi
