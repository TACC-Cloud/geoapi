FROM python:3.7-slim
RUN apt-get update -q && apt-get install -q -y \
  software-properties-common \
  libgdal-dev \
  ffmpeg \
  git
COPY requirements.txt /
RUN pip install --upgrade git+https://github.com/mapillary/mapillary_tools
RUN pip install -q -r /requirements.txt
RUN pip install -q gunicorn
RUN mkdir /app
COPY ./geoapi /app/geoapi
ENV PYTHONPATH "${PYTHONPATH}:/app"
WORKDIR /app/geoapi
