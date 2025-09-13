# Troubleshooting

## Quick Reference

**Common Issues & Solutions:**
- [Build cache problems](#docker-build-cache-issues) - Code changes not taking effect
- [Service connectivity](#docker-specific-troubleshooting) - Services not starting or unreachable
- [Endpoint errors](#service-specific-endpoint-issues) - 404/422 errors from services
- [Memory issues](#libreoffice-memory-leak-solution) - LibreOffice memory accumulation
- [PEP 668 conflicts](#pep-668-externally-managed-environment) - Python package installation errors

## Common Issues

1. **Port conflicts**: Ensure port 8369 is available (other service ports are internal only)
2. **Build failures**: Check Docker installation and disk space
3. **Service connectivity**: Verify network configuration in docker-compose.yml
4. **Permission issues**: Ensure Docker daemon is running and user has proper permissions
5. **Build cache issues**: See [Docker Build Cache Issues](#docker-build-cache-issues)
6. **Requirements corruption**: See [Requirements.txt Corruption](#requirements-txt-corruption)
7. **Package size issues**: See [Unstructured Package Optimization](#unstructured-package-optimization)
8. **Service endpoint errors**: See [Service-Specific Endpoint Issues](#service-specific-endpoint-issues)

## Docker-Specific Troubleshooting

```bash
# Check if Docker daemon is running
docker info

# Reset Docker environment (removes all containers, images, volumes)
docker system prune -a --volumes

# Check Docker disk usage
docker system df
```

If you're using WSL (Ubuntu) and Docker Desktop on Windows, see `docs/DOCKER-DESKTOP-WSL.md` for Docker setup instructions.

## Registry Configuration

If you encounter registry resolution issues:

```bash
# Check Docker daemon status
docker info

# For image pull issues, ensure Docker daemon is running:
```

## Build Issues

```bash
# Clean build cache
docker system prune -a

# Rebuild specific service
docker-compose build pyconvert
```

## PEP 668 (Externally Managed Environment)

If you encounter "externally-managed-environment" errors:

**Solution Applied**: The pandoc service now uses a virtual environment to avoid PEP 668 restrictions in Alpine Linux.

**Manual Fix** (if needed):
```dockerfile
# In Dockerfile, add:
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --break-system-packages package_name
```

**Why This Happens**: Alpine Linux enforces PEP 668 to prevent conflicts with system package management.

## Logs

```bash
# View all logs
docker-compose logs

# View specific service logs
docker-compose logs proxy
docker-compose logs unstructured-io

# Follow logs in real-time
docker-compose logs -f
```

## Image Tag Issues

If you encounter "manifest unknown" errors:

**LibreOffice Image:**
```yaml
# Use specific version instead of latest
image: docker.io/libreofficedocker/libreoffice-unoserver:3.19
```

**Available LibreOffice tags:** `3.19`, `3.18`, `3.17`, `3.16`, `3.15`, `3.14`

## Entrypoint Conflicts

If services fail to start with "Unknown option" errors:

**Pandoc Service:**
- The Dockerfile now includes `ENTRYPOINT []` to override the default pandoc entrypoint
- Uses virtual environment path for uvicorn: `/opt/venv/bin/uvicorn`

## CNI Configuration Warnings

The warnings about "plugin firewall does not support config version" are non-critical:
- These are Docker networking warnings
- Services will still function normally
- Can be ignored unless networking issues occur

## LibreOffice Memory Leak Solution

**Issue**: Unoserver has a known memory leak that causes memory usage to grow indefinitely over time, eventually leading to process termination.

**Root Cause Identified**: Through systematic testing, we discovered that custom environment variables in docker-compose.yml were causing conversion failures. The issue was NOT with unoserver itself, but with conflicting configuration parameters.

**Solution Applied**:
- Removed problematic environment variables (`UNOSERVER_ADDR`, `UNOSERVER_MAX_LIFETIME`, `UNOSERVER_MAX_REQUESTS`, `UNOCONVERT_TIMEOUT`)
- Added `UNOSERVER_STOP_AFTER=50` to restart the process after 50 requests, preventing memory accumulation
- Configured restart policy to handle automatic container recovery

**Testing Results**:
- ✅ Isolated unoserver container: Works perfectly (880ms conversion time)
- ✅ Docker-compose with default config: Works perfectly (531ms conversion time)
- ✅ Docker-compose with memory leak solution: Works perfectly (642ms conversion time)
- ❌ Docker-compose with custom env vars: Fails with "Proxy error" and timeouts

**Configuration**:
```yaml
libreoffice:
  image: docker.io/libreofficedocker/libreoffice-unoserver:3.19
  environment:
    - UNOSERVER_STOP_AFTER=50  # Restart after 50 requests to prevent memory leaks
  deploy:
    restart_policy:
      condition: on-failure
      delay: 5s
      max_attempts: 3
      window: 120s
  networks:
    - app-network
```

**Why This Works**:
- The `--stop-after` parameter (added in unoserver 3.2) is the official solution for memory leaks
- Automatic container restart ensures continuous service availability
- No performance impact on individual conversions
- Prevents memory accumulation that causes system instability