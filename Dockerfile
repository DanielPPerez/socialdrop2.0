# Builder stage
FROM python:3.11-slim AS builder
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir hatchling
RUN pip install --no-cache-dir -e ".[youtube,bluesky,watch]"

# Runtime stage
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/socialdrop /app/src/socialdrop
COPY pyproject.toml /app/pyproject.toml
ENV PYTHONPATH=/app/src
ENTRYPOINT ["socialdrop"]
CMD ["--help"]
