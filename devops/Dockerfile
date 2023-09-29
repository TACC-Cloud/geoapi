FROM python:3.9-slim
RUN apt-get update -q && apt-get install -q -y \
  build-essential \
  software-properties-common \
  libgdal-dev \
  ffmpeg \
  curl \
  git

ENV POETRY_VERSION=1.4.2
ENV POETRY_HOME=/opt/poetry
ENV PATH="$POETRY_HOME/bin:$PATH"
RUN curl -sSL https://install.python-poetry.org | python3 -
RUN poetry config virtualenvs.create false

RUN mkdir /app
WORKDIR /app

COPY devops/poetry.lock devops/pyproject.toml ./
RUN poetry install

COPY geoapi /app/geoapi
ENV PYTHONPATH "${PYTHONPATH}:/app"
WORKDIR /app/geoapi
