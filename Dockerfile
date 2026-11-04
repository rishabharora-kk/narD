FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml /app/
COPY nard /app/nard
RUN pip install --no-cache-dir .
COPY sources.json /app/sources.json
RUN useradd --uid 10001 --create-home nard && mkdir -p /data && chown nard:nard /data
USER nard
