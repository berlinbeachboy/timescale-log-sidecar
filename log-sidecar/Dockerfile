FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install system dependencies
RUN apt-get update \
  && apt-get -y install postgresql-client wget grep \
  && apt-get clean


# Get and install logging sidecar
RUN mkdir -p /log-sidecar

WORKDIR /log-sidecar/

# install python dependencies
COPY requirements.txt /log-sidecar/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . /log-sidecar

ENV PYTHONPATH=/log-sidecar