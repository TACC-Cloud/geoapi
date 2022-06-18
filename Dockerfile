FROM python:3.9-slim
RUN apt-get update -q && apt-get install -q -y \
  software-properties-common \
  libgdal-dev \
  ffmpeg \
  curl \
  git

ENV POETRY_VERSION=1.1.13
ENV POETRY_HOME=/opt/poetry
ENV PATH="$POETRY_HOME/bin:$PATH"
RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python -
RUN poetry config virtualenvs.create false
COPY pyproject.toml poetry.lock ./
RUN poetry install

RUN mkdir /app
COPY ./geoapi /app/geoapi
ENV PYTHONPATH "${PYTHONPATH}:/app"
WORKDIR /app/geoapi
