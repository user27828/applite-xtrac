FROM docker.io/library/python:3.11-slim

# Install system dependencies (removed WeasyPrint dependencies as it's now in pyconvert-service)
RUN apt-get update && apt-get install -y \
    libgtk-3-0 \
    libcairo2 \
    libpango-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

# Add timestamp to force cache invalidation
ARG BUILD_DATE
RUN echo "Build date: $BUILD_DATE"

COPY . /app/

EXPOSE 8369

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8369"]