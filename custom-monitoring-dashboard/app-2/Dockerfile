From python:3.10.2-slim-buster

WORKDIR /app-2

COPY requirements.txt .

RUN pip3 install -r requirements.txt

COPY main.py .

EXPOSE 8000, 9090

