FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py bot_texts.py .
COPY welcome.png .
CMD ["python", "main.py"]
