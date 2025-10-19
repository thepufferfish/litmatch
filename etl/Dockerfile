FROM python:3.11-slim
WORKDIR /etl
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
 && rm -rf /var/lib/apt/lists/*
COPY ./requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . /etl
RUN /etl/etl_runner.py