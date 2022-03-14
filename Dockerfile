FROM python:3.8-slim
RUN apt-get update -q && apt-get install -q -y \
  software-properties-common \
  libgdal-dev \
  ffmpeg
COPY requirements.txt /
RUN pip install -q -r /requirements.txt
RUN mkdir /app
COPY ./geoapi /app/geoapi
ENV PYTHONPATH "${PYTHONPATH}:/app"
WORKDIR /app/geoapi
