FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=8080

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a non-root user.
RUN useradd --create-home --uid 1000 pocketsmart \
    && mkdir -p /app/data \
    && chown -R pocketsmart:pocketsmart /app
USER pocketsmart

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/api/health')"

CMD ["sh", "-c", "gunicorn \"wsgi:application\" --bind 0.0.0.0:${PORT} --workers 2 --threads 4 --timeout 120 --access-logfile -"]
