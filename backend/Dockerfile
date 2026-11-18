FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APS_DATABASE_URL=sqlite:////data/app.db

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY db ./db

VOLUME /data
EXPOSE 8000

# 启动前导入预设样例（可重复执行，只重置 is_seed=1 的讨论），再起服务
CMD ["sh", "-c", "python -m db.seed && uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000"]
