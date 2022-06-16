FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
# install system dependencies

# install python dependencies
RUN mkdir -p /test-api
WORKDIR /test-api/
COPY requirements.txt /test-api/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . /test-api

ENV PYTHONPATH=/test-api