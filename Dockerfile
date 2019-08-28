FROM python:3.7-slim
RUN apt-get update -q && apt-get install -q -y \
  git \
  make \
  g++ \
  software-properties-common \
  libgdal-dev \
  ffmpeg

# Add lasinfo (LAStools)
WORKDIR /opt
RUN git clone --depth 1 https://github.com/LAStools/LAStools && cd LAStools/ && make all && make clean && rm -rf data && find bin/ ! -name 'lasinfo' -type f -exec rm -f {} +
ENV PATH /opt/LAStools/bin/:$PATH

COPY requirements.txt /
WORKDIR /opt
RUN pip install -q -r /requirements.txt
RUN pip install -q gunicorn
RUN mkdir /app
COPY ./geoapi /app/geoapi
ENV PYTHONPATH "${PYTHONPATH}:/app"

WORKDIR /app/geoapi
