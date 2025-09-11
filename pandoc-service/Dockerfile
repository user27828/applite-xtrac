FROM docker.io/pandoc/extra:latest

# Install Python and pip
RUN apk add --no-cache python3 py3-pip

# Install libmagic (required for python-magic)
RUN apk add --no-cache libmagic file

# Create virtual environment
RUN python3 -m venv /opt/venv

# Activate virtual environment and install packages
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install fastapi uvicorn python-multipart python-magic

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