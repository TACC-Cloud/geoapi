FROM python:3.9-slim
RUN apt-get update -q && apt-get install -q -y \
  build-essential \
  software-properties-common \
  libgdal-dev \
  ffmpeg \
  curl \
  git

ENV POETRY_VERSION=1.8.3
ENV POETRY_HOME=/opt/poetry
ENV PATH="$POETRY_HOME/bin:$PATH"
RUN curl -sSL https://install.python-poetry.org | python3 -
RUN poetry config virtualenvs.create false

WORKDIR /opt
COPY devops/poetry.lock devops/pyproject.toml ./
RUN poetry install

RUN mkdir /app
COPY geoapi /app/geoapi
ENV PYTHONPATH=/app

WORKDIR /app/geoapi
