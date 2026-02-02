# Sử dụng Python 3.10
FROM python:3.10-slim

# Cài đặt FFmpeg và Git (cần thiết cho yt-dlp)
RUN apt-get update && \
    apt-get install -y ffmpeg git && \
    rm -rf /var/lib/apt/lists/*

# Thiết lập thư mục làm việc
WORKDIR /app

# Copy file requirements và cài thư viện
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code vào
COPY . .

# Lệnh chạy bot
CMD ["python", "main.py"]
