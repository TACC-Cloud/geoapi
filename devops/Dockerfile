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

# use local mapillary (instead of directly from github in pyproject.toml)
# due to issues with worker image environment
RUN git clone https://github.com/mapillary/mapillary_tools.git /opt/mapillary_source
RUN cd /opt/mapillary_source && git checkout 4bfebf8

WORKDIR /opt
COPY devops/poetry.lock devops/pyproject.toml ./
RUN poetry install

RUN mkdir /app
COPY geoapi /app/geoapi
ENV PYTHONPATH "${PYTHONPATH}:/app"
WORKDIR /app/geoapi
