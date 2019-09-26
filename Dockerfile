FROM python:3.7-slim
#RUN apt-get install -q -y software-properties-common
RUN apt-get update -qq \
    && apt-get install -qq -y libgdal-dev ffmpeg \
    && apt-get clean -qq
RUN mkdir /app
COPY requirements.txt /
RUN pip install -q -r requirements.txt
RUN pip install -q gunicorn
COPY ./geoapi /app/geoapi
ENV PYTHONPATH "${PYTHONPATH}:/app"
WORKDIR /app/geoapi
