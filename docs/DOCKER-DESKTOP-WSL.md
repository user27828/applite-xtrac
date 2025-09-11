# Docker Setup Guide for AppLite Convert

This guide provides comprehensive instructions for setting up Docker in different environments to run the AppLite Convert multi-service document processing API. Docker Desktop on Windows automatically exposes Docker runtimes to WSL distributions, while Ubuntu/Debian systems require direct Docker Engine installation.

## 1. Windows + WSL (Docker Desktop)

Docker Desktop for Windows provides seamless integration with WSL 2 distributions. When you enable WSL integration in Docker Desktop settings, it automatically:

- Creates special WSL distributions (`docker-desktop` and `docker-desktop-data`)
- Shares the Docker daemon socket with integrated WSL distributions
- Allows WSL distributions to access Docker commands without additional setup

### Installation Steps

1. **Install Docker Desktop for Windows**
   - Download from: https://www.docker.com/products/docker-desktop
   - Run the installer and follow the setup wizard
   - Docker Desktop will automatically detect and enable WSL 2 during installation

2. **Enable WSL Integration**
   - Open Docker Desktop
   - Go to Settings → Resources → WSL Integration
   - Enable integration for your Ubuntu/WSL distribution
   - Click "Apply & Restart"

3. **Verify Setup**
   ```bash
   # In your WSL terminal
   docker --version
   docker run hello-world
   ```

### How Automatic Runtime Exposure Works

Docker Desktop automatically:
- Creates a `docker-desktop` WSL distribution that runs the Docker daemon
- Shares the Docker socket (`/var/run/docker.sock`) with integrated WSL distributions
- Manages container storage in a `docker-desktop-data` VHDX file
- Provides seamless access to Docker commands from within WSL

### Benefits of WSL Integration

- **No additional installation** required in WSL distributions
- **Automatic socket sharing** between Windows and WSL
- **Unified container management** across Windows and Linux environments
- **Performance optimizations** for file system operations

## 2. Ubuntu/Debian (Native Linux)

For Ubuntu or Debian systems (not running in WSL), install Docker Engine directly using the official Docker repository.

### Installation Steps

1. **Uninstall old versions**
   ```bash
   for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do
     sudo apt-get remove $pkg
   done
   ```

2. **Set up Docker repository**
   ```bash
   # Add Docker's official GPG key
   sudo apt-get update
   sudo apt-get install ca-certificates curl gnupg
   sudo install -m 0755 -d /etc/apt/keyrings
   sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
   sudo chmod a+r /etc/apt/keyrings/docker.asc

   # Add the repository to Apt sources
   echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
   sudo apt-get update
   ```

3. **Install Docker Engine**
   ```bash
   sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
   ```

4. **Add user to docker group (optional)**
   ```bash
   sudo usermod -aG docker $USER
   # Log out and back in for changes to take effect
   ```

5. **Verify installation**
   ```bash
   sudo docker run hello-world
   ```

### Alternative: Convenience Script

For quick installation on development systems:

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

## 3. AppLite Convert Setup

### Clone and Setup Project

```bash
# Clone the repository
git clone <repository-url>
cd applite-xtrac

# Make scripts executable
chmod +x run.sh tests/test-network-performance.sh tests/test-performance.sh

# Start development mode (recommended for development)
./run.sh dev

# Or start all services in containers
./run.sh up
```

### Development Mode vs Production Mode

**Development Mode** (`./run.sh dev`):
- Proxy service runs locally on host (port 8369)
- Conversion services run in Docker containers
- Hot reload enabled for proxy development
- Faster for development workflow
- **Recommended for development**

**Production Mode** (`./run.sh up`):
- All services run in Docker containers
- Complete container isolation
- Better for production deployment
- Slower startup but more stable

### Network Configuration

The project uses optimized Docker networking:

```yaml
networks:
  app-network:
    driver: bridge
    driver_opts:
      com.docker.network.bridge.name: applite-bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
          gateway: 172.20.0.1
```

This configuration provides:
- **Custom bridge network** for better isolation
- **Optimized IP addressing** to avoid conflicts
- **Performance improvements** for host-container communication

## 4. Using Docker Compose

Both setups support Docker Compose:

```bash
# Check compose version
docker compose version

# Or legacy syntax
docker-compose version

# Both work identically
docker compose up
docker-compose up
```

### Available Commands

```bash
# Development mode (recommended)
./run.sh dev

# Production mode
./run.sh up

# Stop all services
./run.sh down

# View logs
./run.sh logs

# Check service status
./run.sh status

# Test network performance
./tests/test-network-performance.sh
```

## 5. Troubleshooting

### WSL-Specific Issues

- **WSL version**: Ensure you're using WSL 2 (run `wsl -l -v` to check)
- **Integration not working**: Restart Docker Desktop and WSL terminal
- **File permissions**: Ensure your user has access to Docker socket
- **Slow performance**: Store project files in WSL filesystem (`~/project`) not Windows mounts (`/mnt/c/`)

### Ubuntu/Debian Issues

- **Permission denied**: Run with `sudo` or add user to docker group
- **Service not starting**: `sudo systemctl start docker`
- **Firewall conflicts**: Docker may conflict with ufw/firewalld

### AppLite Convert Specific Issues

- **Port conflicts**: Check if ports 8000, 2004, 3000, 3001, 8369 are available
- **Slow responses**: Run `./tests/test-network-performance.sh` to diagnose network issues
- **Container startup failures**: Check Docker Desktop resource allocation
- **Network timeouts**: Ensure Docker Desktop networking is properly configured

### General Troubleshooting

```bash
# Check Docker service status
sudo systemctl status docker

# View Docker logs
sudo journalctl -u docker

# Test basic functionality
docker run --rm hello-world

# Check AppLite Convert services
curl http://localhost:8369/ping
curl http://localhost:8369/ping-all
```

## 6. Performance Optimization

### Docker Desktop Settings

For optimal performance with AppLite Convert:

1. **Resources** → **Advanced**:
   - Allocate at least 4GB RAM
   - Allocate at least 2 CPU cores
   - Allocate at least 20GB disk space

2. **Docker Engine** (Advanced):
   ```json
   {
     "features": {
       "buildkit": true
     },
     "builder": {
       "gc": {
         "enabled": true,
         "defaultKeepStorage": "20GB"
       }
     }
   }
   ```

### Network Optimization

The project includes network optimizations for development:

- **Connection pooling** to reduce latency
- **Keep-alive connections** for better performance
- **IPv4 prioritization** to avoid DNS resolution delays
- **Optimized timeouts** for development workflow

### Development Workflow

```bash
# Start development mode
./run.sh dev

# Test API endpoints
curl http://localhost:8369/ping
curl http://localhost:8369/convert/supported

# Monitor performance
./tests/test-network-performance.sh

# View logs
./run.sh logs
```

## 7. Best Practices

- **WSL**: Store source code in the Linux filesystem (`~/project`) rather than Windows mounts (`/mnt/c/`)
- **Security**: Use Docker's built-in security features rather than relying on WSL isolation
- **Performance**: Enable Docker Desktop's WSL 2 backend for best performance
- **Updates**: Keep Docker Desktop updated for latest WSL integration improvements
- **Development**: Use `./run.sh dev` for development with hot reload
- **Monitoring**: Regularly run `./tests/test-network-performance.sh` to monitor performance
- **Cleanup**: Use `./run.sh down` to properly stop all services
