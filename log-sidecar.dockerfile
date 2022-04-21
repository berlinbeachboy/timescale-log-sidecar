FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONBUFFERED 1

# install system dependencies
RUN apt-get update \
  && apt-get -y install postgresql-client \
  && apt-get clean

# install python dependencies
RUN mkdir -p /log-sidecar
WORKDIR /log-sidecar/
COPY requirements.txt /log-sidecar/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy starting scripts and make them executable
COPY shell_scripts/start.sh /start.sh
RUN chmod +x /start.sh
COPY shell_scripts/setup_db.sh /setup_db.sh
RUN chmod +x /setup_db.sh

# Copy starting scripts and make them executable
COPY . /log-sidecar


ENV PYTHONPATH=/log-sidecar

# Either uncomment this or add command in docker-compose.yml
#CMD [ "python", "./main.py"]