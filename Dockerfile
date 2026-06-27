FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY analyzer.py bot.py config.py errors.py formatting.py main.py prompts.py storage.py ./

RUN mkdir -p /app/data

CMD ["python", "main.py"]
