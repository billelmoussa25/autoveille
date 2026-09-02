FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    DB_PATH=/srv/data/annonces.sqlite3 \
    CONFIG_PATH=/srv/config.yml

WORKDIR /srv
RUN mkdir -p /srv/data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
