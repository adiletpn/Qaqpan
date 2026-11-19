FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY api/ api/
COPY data/ data/
COPY web/public/samples/ web/public/samples/
COPY --from=web /web/dist/ web/dist/
ENV PORT=8000 PYTHONUNBUFFERED=1
EXPOSE 8000
# one worker: demo state lives in memory
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT} --workers 1"]
