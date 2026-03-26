# vecgate/docker/Dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/
COPY sql/ sql/

RUN pip install --no-cache-dir -e ".[all]"

EXPOSE 8000

CMD ["vecgate", "serve", "--host", "0.0.0.0", "--port", "8000"]
