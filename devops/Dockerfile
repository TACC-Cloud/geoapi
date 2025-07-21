FROM python:3.12-slim AS python-base

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
ENV POETRY_VERSION=2.1.3 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    PYSETUP_PATH="/opt/pysetup" \
    VENV_PATH="/opt/pysetup/.venv"

# prepend venv and poetry to path
ENV PATH="$VENV_PATH/bin:$POETRY_HOME/bin:$PATH"

# Install poetry version $POETRY_VERSION to $POETRY_HOME
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel \
    && python3 -m venv "$POETRY_HOME" \
    && "$POETRY_HOME/bin/pip" install --no-cache-dir poetry~="$POETRY_VERSION"

# Copy project requirement files to ensure they will be cached.
WORKDIR $PYSETUP_PATH
COPY devops/poetry.lock devops/pyproject.toml ./

# install runtime deps - uses $POETRY_VIRTUALENVS_IN_PROJECT internally
RUN poetry install

##############
# `development` image target is used for local development
FROM python-base AS development

# copy in our built poetry + venv
COPY --from=python-base $POETRY_HOME $POETRY_HOME
COPY --from=python-base $PYSETUP_PATH $PYSETUP_PATH

# Install dev dependencies
RUN poetry install --with dev

COPY geoapi /app/geoapi

ENV PYTHONPATH=/app

WORKDIR /app/geoapi

##############
# `production` image target is used for deployed runtime environments
FROM python-base AS production

# Install runtime dependencies
COPY --from=python-base $PYSETUP_PATH $PYSETUP_PATH

COPY geoapi /app/geoapi

ENV PYTHONPATH=/app

WORKDIR /app/geoapi
