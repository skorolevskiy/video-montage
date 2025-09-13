FROM python:3.9-slim
RUN apt-get update 
RUN apt-get install -y ffmpeg gdown
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
WORKDIR /app
EXPOSE 8000

