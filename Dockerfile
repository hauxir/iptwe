FROM python:3.9-slim

RUN apt-get update
RUN apt-get install -y ffmpeg nginx mediainfo

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 5000

COPY app /app

WORKDIR /app

CMD bash entrypoint.sh
