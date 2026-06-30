FROM python:3.11-slim

WORKDIR /app

COPY labeling/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY labeling/backend/main.py .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
