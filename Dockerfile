FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

RUN pip install --upgrade pip && \
    pip install . && \
    pip install pylatexenc

RUN mkdir -p /app/output

ENTRYPOINT ["qupepfold"]

CMD ["--help"]
