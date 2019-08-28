FROM python:3.7-slim
RUN apt-get update -q && apt-get install -q -y \
  software-properties-common \
  libgdal-dev \
  ffmpeg

# Add lasinfo (LAStools)
WORKDIR /opt
RUN git clone https://github.com/LAStools/LAStools && cd LAStools/ && make all && make clean && rm -rf data && find bin/ ! -name 'lasinfo' -type f -exec rm -f {} +
ENV PATH /opt/LAStools/bin/:$PATH

RUN mkdir /app
COPY requirements.txt /
RUN pip install -q -r requirements.txt
RUN pip install -q gunicorn
COPY ./geoapi /app/geoapi
ENV PYTHONPATH "${PYTHONPATH}:/app"
WORKDIR /app/geoapi
