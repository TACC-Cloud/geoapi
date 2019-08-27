FROM python:3.7-slim
RUN apt-get update -q
RUN apt-get install -q -y software-properties-common
RUN apt-get install -y libgdal-dev ffmpeg cmake

# Install lasinfo (LASTool)
WORKDIR /opt
RUN git clone https://github.com/LAStools/LAStools && cd LAStools/ && make all && make clean && rm -rf data && find bin/ ! -name 'lasinfo' -type f -exec rm -f {} +
ENV PATH /opt/LAStools/bin/:$PATH

COPY requirements.txt /
RUN pip install -q -r requirements.txt
RUN pip install -q gunicorn

WORKDIR /opt

RUN mkdir /app
COPY ./geoapi /app/geoapi
ENV PYTHONPATH "${PYTHONPATH}:/app"
WORKDIR /app/geoapi
