# Slim production image — Gemini API embeddings, no sentence-transformers.
FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    EMBEDDING_BACKEND=gemini \
    PORT=8080

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
COPY src ./src

RUN uv pip install --system .

EXPOSE 8080

CMD ["kairos", "serve", "--host", "0.0.0.0", "--port", "8080"]
