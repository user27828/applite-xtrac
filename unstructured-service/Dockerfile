FROM downloads.unstructured.io/unstructured-io/unstructured-api:latest@sha256:1511990f121851152c144fc64eca58da47b7acf7e1b5ab298207f4236ad3e2dc

# The upstream lifetime wrapper uses GNU timeout's --preserve-status flag,
# while the current Wolfi image exposes BusyBox timeout. Install the compatible
# implementation so the documented MAX_LIFETIME_SECONDS guard can start.
USER root
RUN apk add --no-cache coreutils
USER notebook-user
