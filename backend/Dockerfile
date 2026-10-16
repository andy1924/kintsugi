FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.lock ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home kintsugi && mkdir /data && chown kintsugi /data
COPY --chown=kintsugi backend/ /app/
USER kintsugi
ENV DATA_DIR=/data
CMD ["uvicorn", "kintsugi.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
