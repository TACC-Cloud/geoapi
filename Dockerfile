FROM python:3.7
COPY . /api
RUN pip install -r /api/requirements.txt
RUN pip install gunicorn
ENV PYTHONPATH "${PYTHONPATH}:/api"
WORKDIR /api
