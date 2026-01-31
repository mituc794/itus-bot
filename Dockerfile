FROM python:3.10-slim

# Cài đặt FFmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

# Cài thư viện
RUN pip install --no-cache-dir -r requirements.txt

# Chạy bot
CMD ["python", "main.py"]
