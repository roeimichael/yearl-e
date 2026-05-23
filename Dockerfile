FROM python:3.11-slim

WORKDIR /app

# System lib shapely's GEOS extension needs at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgeos-c1v5 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY data/region_sets/ data/region_sets/
COPY data/year_scores/ data/year_scores/

EXPOSE 8000
CMD sh -c "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"
