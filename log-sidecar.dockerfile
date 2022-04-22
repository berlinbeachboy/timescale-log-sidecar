FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONBUFFERED 1

# install system dependencies
RUN apt-get update \
  && apt-get -y install postgresql-client wget \
  && apt-get clean


# Get and install logging sidecar
RUN mkdir -p /log-sidecar
RUN wget https://github.com/berlinbeachboy/timescale-log-sidecar/archive/refs/tags/v0.0.1-alpha.2.tar.gz && \
    tar -xvf v0.0.1-alpha.2.tar.gz && \
    cp timescale-log-sidecar-0.0.1-alpha.2/* /log-sidecar/ &&\
    rm v0.0.1-alpha.2.tar.gz && \
    rm -r timescale-log-sidecar-0.0.2-alpha.2

WORKDIR /log-sidecar/

# install python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy starting scripts to root directory
RUN chmod +x start.sh
RUN chmod +x setup_db.sh

ENV PYTHONPATH=/log-sidecar

# Either uncomment this or add command `/log-sidecar/start.sh` in docker-compose.yml
#CMD [ "python", "./main.py"]