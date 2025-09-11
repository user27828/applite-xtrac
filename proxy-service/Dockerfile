FROM docker.io/library/python:3.11-slim

# Install system dependencies for WeasyPrint
RUN apt-get update && apt-get install -y \
    libgtk-3-0 \
    libcairo2 \
    libpango-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libgobject-2.0-0 \
    libglib2.0-0 \
    libgirepository1.0-dev \
    gir1.2-gtk-3.0 \
    libcairo-gobject2 \
    libpangocairo-1.0-0 \
    fonts-liberation \
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