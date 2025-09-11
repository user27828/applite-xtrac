FROM docker.io/pandoc/extra:latest

# Install Python and pip
RUN apk add --no-cache python3 py3-pip

# Install libmagic (required for python-magic)
RUN apk add --no-cache libmagic file

# Install system dependencies for WeasyPrint
RUN apk add --no-cache \
    cairo \
    cairo-dev \
    pango \
    pango-dev \
    gdk-pixbuf \
    gdk-pixbuf-dev \
    libffi-dev \
    jpeg-dev \
    libxml2-dev \
    libxslt-dev \
    zlib-dev \
    fontconfig \
    ttf-dejavu \
    ttf-liberation \
    ttf-freefont

# Create virtual environment
RUN python3 -m venv /opt/venv

# Activate virtual environment and install packages
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# Create app directory
WORKDIR /app

# Copy the API script and utils directory
COPY app.py /app/app.py
COPY utils/ /app/utils/

# Expose port
EXPOSE 3000

# Override any default entrypoint and run the API
ENTRYPOINT []
CMD ["/opt/venv/bin/uvicorn", "app:app", "--host", "0.0.0.0", "--port", "3000"]