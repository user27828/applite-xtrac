# Podman WSL Setup (Static Binary Method)

This guide provides a reliable method to install a full-featured Podman CLI on an Ubuntu WSL instance by using the official static binary, bypassing apt repository issues. It also includes the steps to connect to a separate Podman service, such as the one managed by Podman Desktop.

## 1. Install the Podman Static Binary

Use these commands to download, install, and clean up the latest Podman static binary from its official GitHub releases page.

```bash
# Download the latest Podman static binary
curl -L -o podman-static.tar.gz https://github.com/containers/podman/releases/download/v5.6.0/podman-static-linux_amd64.tar.gz

# Full release list: https://github.com/containers/podman/releases/

# Unpack the archive
tar -xzf podman-static.tar.gz

# Move the executable to a standard location in your PATH
sudo mv podman-static-linux_amd64/podman /usr/local/bin/podman

# Clean up the downloaded files
rm -rf podman-static-linux_amd64 podman-static.tar.gz
```

## 2. Configure the Connection

Run the following command as your regular user (without sudo) to create a saved connection profile that points to the Podman service running in your other WSL instance.

```bash
podman system connection add --default podman-machine-default unix:///mnt/wsl/podman-sockets/podman-machine-default/podman-user.sock
```

To verify that the connection has been successfully created, run:

```bash
podman system connection list
```

## 3. Verify the Installation

Confirm that your podman command is now correctly configured and connected to the remote service by running a simple test command.

```bash
podman info
```

If the output includes `serviceIsRemote: true`, you are now seamlessly using Podman from your Ubuntu WSL instance.

---

Notes:
- This method uses a release binary to avoid distribution packaging issues. Update the release URL to a newer version if needed.
- The socket path used in the connection command (`/mnt/wsl/podman-sockets/...`) assumes Podman Desktop or another WSL-hosted Podman is exposing its user socket there; adapt the path to match your environment.
