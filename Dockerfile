FROM python:3.7-slim
RUN apt-get update
RUN apt-get install -y software-properties-common
RUN apt-get install -y libgdal-dev ffmpeg
RUN mkdir /app
COPY requirements.txt /
RUN pip install -r requirements.txt
RUN pip install gunicorn
COPY ./geoapi /app/geoapi
ENV PYTHONPATH "${PYTHONPATH}:/app"
WORKDIR /app/geoapi
