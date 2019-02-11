FROM python:3.7
COPY . /api
RUN pip install -r /api/requirements.txt
ENV PYTHONPATH "${PYTHONPATH}:/api"
WORKDIR /api
