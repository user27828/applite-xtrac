# syntax=docker/dockerfile:1
FROM docker.io/library/python:3.11.17-slim-bookworm

# python-magic is the proxy's only native runtime dependency. Rendering
# libraries live in pyconvert-service and do not belong in this image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN --mount=type=cache,id=applite-xtrac-proxy-pip,target=/root/.cache/pip,sharing=locked \
    pip install -r requirements.txt

# Add timestamp to force cache invalidation
ARG BUILD_DATE
RUN echo "Build date: $BUILD_DATE"

COPY . /app/

EXPOSE 8369

CMD ["python", "app.py"]
