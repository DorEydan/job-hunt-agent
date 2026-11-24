# Control panel + resume tools in a container. PDF export uses LibreOffice instead of Microsoft Word.
# The agent itself still runs in Claude Code on your computer (it needs your browser for job sites).
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libreoffice-writer-nogui \
       fonts-liberation fonts-dejavu-core fonts-noto-core fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a normal user. HOME must be writable for LibreOffice.
RUN useradd --create-home --uid 1000 app && chown -R app /app
USER app
ENV HOME=/home/app \
    PYTHONUNBUFFERED=1 \
    JOBHUNT_PDF_ENGINE=libreoffice \
    JOBHUNT_IN_DOCKER=1

EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8765/api/ping', headers={'Host': '127.0.0.1:8765'}), timeout=4)"

# Inside the container it listens on all interfaces; docker-compose publishes it on 127.0.0.1 only.
CMD ["python", "ui/server.py", "--host", "0.0.0.0", "--port", "8765", "--no-browser"]
