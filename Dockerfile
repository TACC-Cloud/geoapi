FROM python:3.7
RUN apt-get update
RUN apt-get install -y software-properties-common
RUN apt-get install -y libgdal-dev ffmpeg cmake
RUN mkdir /api
COPY ./geoapi /api
COPY requirements.txt /
RUN pip install -r requirements.txt
RUN pip install gunicorn
ENV PYTHONPATH "${PYTHONPATH}:/api"
WORKDIR /opt
RUN git clone https://github.com/LAStools/LAStools && cd LAStools/ && make all && cd .. && rm -rf LAStools
ENV PATH /opt/LAStools/bin/:$PATH
WORKDIR /api
