FROM python:3.7
RUN apt-get update
RUN apt-get install -y software-properties-common
RUN apt-get install -y libgdal-dev
COPY . /api
RUN pip install -r /api/requirements.txt
RUN pip install gunicorn
ENV PYTHONPATH "${PYTHONPATH}:/api"
WORKDIR /api
