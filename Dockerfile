FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    cmake \
    && rm -rf /var/lib/apt/lists/*


COPY . .


RUN pip install --upgrade pip

RUN pip install \
    -r requirements-service.txt


RUN pip install -e .


RUN mkdir -p /app/output/jobs


EXPOSE 8000


CMD [
"uvicorn",
"app:app",
"--host",
"0.0.0.0",
"--port",
"8000"
]
