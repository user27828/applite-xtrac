FROM downloads.unstructured.io/unstructured-io/unstructured-api:0.1.15@sha256:9d4496a7312c6c17490231cd9d7e5592a1edbe83a0098ce52ec8a88cdcb12235

# The upstream lifetime wrapper uses GNU timeout's --preserve-status flag,
# while the current Wolfi image exposes BusyBox timeout. Install the compatible
# implementation so the documented MAX_LIFETIME_SECONDS guard can start.
USER root
RUN apk add --no-cache coreutils
USER notebook-user
