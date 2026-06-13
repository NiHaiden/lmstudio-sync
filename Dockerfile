FROM python:3.12-alpine

RUN pip install --no-cache-dir requests

COPY sync.py /app/sync.py

CMD ["python", "/app/sync.py"]
