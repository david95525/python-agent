FROM python:3.12-slim-bookworm

# 複製 uv 執行檔
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 複製依賴文件
COPY pyproject.toml uv.lock ./

# 安裝依賴到系統路徑 (節省空間)
RUN uv pip install --system --no-cache -r pyproject.toml

# 複製專案文件
COPY . .

# 建立必要目錄
RUN mkdir -p logs data && chmod -R 777 logs data

ENV PYTHONUNBUFFERED=1

# 暴露埠號
EXPOSE 8000

# 啟動指令：使用 uvicorn 確保非同步性能，並動態綁定 Railway 的 Port
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]