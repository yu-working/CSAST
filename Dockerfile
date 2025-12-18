FROM python:3.10-slim AS builder
# install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# setting workdir
WORKDIR /app

# 複製依賴清單
COPY requirements.txt .

# 設定環境變數增加超時到 300 秒 (5 分鐘)
ENV UV_HTTP_TIMEOUT=300

# 使用 uv 安裝套件到系統環境 (加上 --system)
# --no-cache 確保不產生暫存檔，減輕重量
RUN uv pip install --system --no-cache -r requirements.txt

# 第二階段：運行環境 (最終映像檔)
FROM python:3.10-slim
WORKDIR /app

# 從第一階段複製安裝好的套件 (site-packages)
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# copy
COPY app.py .
COPY default_data/FAQ_Default.xlsx /app/default_data/FAQ_Default.xlsx

# 暴露 Streamlit 預設的 8501 埠口
EXPOSE 8501

# 啟動指令 (加上一些參數確保在雲端能正常顯示)
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]