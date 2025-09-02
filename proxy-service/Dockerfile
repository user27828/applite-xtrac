FROM docker.io/library/python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

# Add timestamp to force cache invalidation
ARG BUILD_DATE
RUN echo "Build date: $BUILD_DATE"

COPY . /app/

EXPOSE 8369

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8369"]