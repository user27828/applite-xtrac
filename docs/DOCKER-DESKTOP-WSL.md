# Docker Setup Guide

This guide provides comprehensive instructions for setting up Docker in different environments. Docker Desktop on Windows automatically exposes Docker runtimes to WSL distributions, while Ubuntu/Debian systems require direct Docker Engine installation.

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

## 3. Using Docker Compose

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

## 4. Troubleshooting

### WSL-Specific Issues

- **WSL version**: Ensure you're using WSL 2 (run `wsl -l -v` to check)
- **Integration not working**: Restart Docker Desktop and WSL terminal
- **File permissions**: Ensure your user has access to Docker socket

### Ubuntu/Debian Issues

- **Permission denied**: Run with `sudo` or add user to docker group
- **Service not starting**: `sudo systemctl start docker`
- **Firewall conflicts**: Docker may conflict with ufw/firewalld

### General Troubleshooting

```bash
# Check Docker service status
sudo systemctl status docker

# View Docker logs
sudo journalctl -u docker

# Test basic functionality
docker run --rm hello-world
```

## 5. Best Practices

- **WSL**: Store source code in the Linux filesystem (`~/project`) rather than Windows mounts (`/mnt/c/`)
- **Security**: Use Docker's built-in security features rather than relying on WSL isolation
- **Performance**: Enable Docker Desktop's WSL 2 backend for best performance
- **Updates**: Keep Docker Desktop updated for latest WSL integration improvements
