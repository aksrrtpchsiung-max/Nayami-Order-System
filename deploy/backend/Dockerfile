FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system nayami && adduser --system --ingroup nayami nayami

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY deploy/backend/gunicorn.conf.py ./gunicorn.conf.py
COPY deploy/backend/entrypoint.sh ./entrypoint.sh

USER nayami

EXPOSE 5000

ENTRYPOINT ["sh", "/app/entrypoint.sh"]
CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:app"]
