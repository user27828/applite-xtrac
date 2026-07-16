FROM docker.io/libreofficedocker/libreoffice-unoserver:3.19@sha256:20c6dbf3a35c476e60f1c96a8839e1a67e69f0a0db7298088f791a89a531bb4b

# The base image ships unoserver 1.6, predating conversion deadlines,
# request-count recycling, and multiple upstream memory-leak fixes.
RUN /venv/bin/pip install --no-cache-dir --upgrade "unoserver==3.7"
