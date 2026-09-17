FROM python:3.13-slim

RUN apt-get update \
  && apt-get install -y --no-install-recommends espeak-ng \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY content ./content
COPY main.py .

RUN mkdir -p /app/data /app/data/tts
ENV WORLD_DB_PATH=/app/data/world.sqlite
EXPOSE 8010
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8010"]
