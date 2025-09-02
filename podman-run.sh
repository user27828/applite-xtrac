#!/bin/bash

# Podman-based startup script for the multi-service API
# This script provides an easy way to manage the services with Podman

set -e

COMPOSE_FILE="docker-compose.yml"
PROJECT_NAME="document-api"

case "$1" in
    "up")
        echo "Starting services with Podman..."
        podman-compose -f $COMPOSE_FILE -p $PROJECT_NAME up --build
        ;;
    "up-d")
        echo "Starting services in background with Podman..."
        podman-compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d --build
        ;;
    "down")
        echo "Stopping services..."
        podman-compose -f $COMPOSE_FILE -p $PROJECT_NAME down
        ;;
    "logs")
        if [ -n "$2" ]; then
            podman-compose -f $COMPOSE_FILE -p $PROJECT_NAME logs $2
        else
            podman-compose -f $COMPOSE_FILE -p $PROJECT_NAME logs
        fi
        ;;
    "build")
        echo "Building services..."
        podman-compose -f $COMPOSE_FILE -p $PROJECT_NAME build
        ;;
    "clean")
        echo "Cleaning up containers and volumes..."
        podman-compose -f $COMPOSE_FILE -p $PROJECT_NAME down --volumes
        podman system prune -f
        ;;
    "status")
        echo "Service status:"
        podman-compose -f $COMPOSE_FILE -p $PROJECT_NAME ps
        ;;
    *)
        echo "Usage: $0 {up|up-d|down|logs|build|clean|status} [service]"
        echo ""
        echo "Commands:"
        echo "  up      - Start services (foreground)"
        echo "  up-d    - Start services (background)"
        echo "  down    - Stop services"
        echo "  logs    - Show logs (optionally for specific service)"
        echo "  build   - Build services"
        echo "  clean   - Clean up containers and volumes"
        echo "  status  - Show service status"
        exit 1
        ;;
esac