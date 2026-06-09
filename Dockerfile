FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir tox coverage

COPY pyproject.toml tox.ini ./
COPY src/ src/
COPY tests/ tests/

RUN pip install --no-cache-dir -e ".[dev]"

CMD ["tox"]