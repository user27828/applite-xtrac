# Unstructured image build

The Unstructured service uses the local image `applite-xtrac-unstructured-io:latest`. It is built from the upstream `unstructured-api` source commit recorded in `unstructured-service/upstream-ref`. The build script adds a BuildKit cache mount to the locked `uv sync` step. Installed packages are part of the final image; downloaded package artifacts stay in Docker's builder cache and are excluded from the image layers.

Build or start the service through `run.sh` so the local image exists before Compose starts it:

```bash
./run.sh build unstructured-io
./run.sh up
```

The first build requires Git, Docker BuildKit, and network access to GitHub and the upstream build dependencies. If the image already has the pinned revision label, the build script reuses that image without rebuilding. When a rebuild is needed, BuildKit can reuse downloaded dependencies from the builder cache. This cache is local to the Docker builder, may be removed during cache cleanup, and does not reduce the installed dependencies in the image.

When starting the stack directly with Docker Compose, build the local image first:

```bash
./run.sh build unstructured-io
docker-compose up
```

To force a rebuild while retaining the opportunity to reuse the UV cache mount:

```bash
./run.sh build unstructured-io --no-cache
```

To upgrade the pinned source to the current upstream `main` commit and build it:

```bash
./unstructured-service/update-upstream.sh
```

The script builds from the latest upstream `main` commit and writes the new source pin only after the image builds successfully. Review and validate the new image before deploying. `./run.sh update` pulls the published Gotenberg image; it does not update Unstructured.
