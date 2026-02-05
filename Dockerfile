# 使用官方 Python 輕量版
FROM python:3.10-slim

# 設定工作目錄
WORKDIR /app

# 1. 安裝系統編譯依賴 (psycopg 連線資料庫必備)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 2. 安裝 uv
# 從官方提供的方式快速安裝 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 3. 複製依賴定義文件 (利用 Docker 快取機制)
COPY pyproject.toml uv.lock ./

# 4. 安裝依賴
RUN uv pip install --system --no-cache -r pyproject.toml

# 5. 複製專案其餘檔案 (包含 README.md, app/, static/, data/ 等)
COPY . .

# 6. 安裝專案本身
RUN uv sync --frozen --no-cache

# 7. 建立必要資料夾
RUN mkdir -p logs data

# 8. 環境設定
ENV PYTHONUNBUFFERED=1
# 確保 logs 資料夾權限正常
RUN chmod -R 777 logs

# 暴露埠號
EXPOSE 8000

# 9. 啟動指令
CMD ["python", "main.py"]