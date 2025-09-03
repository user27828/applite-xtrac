#!/bin/bash

# Podman-based startup script for the multi-service API
# This script provides an easy way to manage the services with Podman

set -euo pipefail  # Exit on error, undefined vars, and pipe failures

# Configuration
COMPOSE_FILE="docker-compose.yml"
PROJECT_NAME="applite-convert"
REQUIRED_PORTS=(8369 4000)  # Ports that need to be available
SERVICES=("unstructured-io" "libreoffice" "pandoc" "gotenberg" "proxy")

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Dependency checks
check_dependencies() {
    local missing_deps=()
    
    if ! command -v podman &> /dev/null; then
        missing_deps+=("podman")
    fi
    
    if ! command -v podman-compose &> /dev/null; then
        missing_deps+=("podman-compose")
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        log_error "Missing required dependencies: ${missing_deps[*]}"
        log_info "Please install missing dependencies and try again."
        exit 1
    fi
}

# Configuration validation
validate_config() {
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Docker Compose file '$COMPOSE_FILE' not found!"
        exit 1
    fi
    
    log_info "Configuration validated successfully"
}

# Check port availability
check_ports() {
    local conflicts=()
    
    for port in "${REQUIRED_PORTS[@]}"; do
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            conflicts+=("$port")
        fi
    done
    
    if [ ${#conflicts[@]} -ne 0 ]; then
        log_error "Ports already in use: ${conflicts[*]}"
        log_info "Please stop services using these ports or choose different ports."
        exit 1
    fi
}

# Wait for services to be healthy
wait_for_services() {
    local timeout=${1:-60}
    local interval=${2:-5}
    local elapsed=0
    
    log_info "Waiting for services to be ready..."
    
    while [ $elapsed -lt $timeout ]; do
        local all_healthy=true
        
        for service in "${SERVICES[@]}"; do
            if ! podman-compose -f $COMPOSE_FILE -p $PROJECT_NAME ps $service | grep -q "Up"; then
                all_healthy=false
                break
            fi
        done
        
        if $all_healthy; then
            log_success "All services are ready!"
            return 0
        fi
        
        sleep $interval
        elapsed=$((elapsed + interval))
    done
    
    log_warning "Services may not be fully ready after ${timeout}s"
    return 1
}

# Health check function
check_health() {
    log_info "Checking service health..."
    
    # Try to ping the proxy service
    if curl -s -f http://localhost:8369/ping >/dev/null 2>&1; then
        log_success "Proxy service is responding"
        
        # Check individual services via proxy
        if curl -s -f http://localhost:8369/ping-all >/dev/null 2>&1; then
            log_success "All services are healthy"
        else
            log_warning "Some services may be unhealthy"
        fi
    else
        log_error "Proxy service is not responding"
        return 1
    fi
}

# Show resource usage
show_resources() {
    log_info "Container resource usage:"
    podman stats --no-stream $(podman-compose -f $COMPOSE_FILE -p $PROJECT_NAME ps -q)
}

# Pull latest images
update_images() {
    log_info "Pulling latest images..."
    podman-compose -f $COMPOSE_FILE -p $PROJECT_NAME pull
    log_success "Images updated successfully"
}

# Service-specific operations
manage_service() {
    local action=$1
    local service=$2
    
    if [[ ! " ${SERVICES[*]} " =~ " ${service} " ]]; then
        log_error "Unknown service: $service"
        log_info "Available services: ${SERVICES[*]}"
        exit 1
    fi
    
    case $action in
        start)
            log_info "Starting service: $service"
            podman-compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d $service
            ;;
        stop)
            log_info "Stopping service: $service"
            podman-compose -f $COMPOSE_FILE -p $PROJECT_NAME stop $service
            ;;
        restart)
            log_info "Restarting service: $service"
            podman-compose -f $COMPOSE_FILE -p $PROJECT_NAME restart $service
            ;;
        logs)
            podman-compose -f $COMPOSE_FILE -p $PROJECT_NAME logs -f $service
            ;;
        *)
            log_error "Unknown action: $action"
            exit 1
            ;;
    esac
}

# Main command processing
main() {
    local command=$1
    shift
    
    case "$command" in
        "up")
            check_dependencies
            validate_config
            check_ports
            log_info "Starting services with Podman..."
            podman-compose -f $COMPOSE_FILE -p $PROJECT_NAME up --build "$@"
            wait_for_services
            check_health
            ;;
        "up-d")
            check_dependencies
            validate_config
            check_ports
            log_info "Starting services in background with Podman..."
            podman-compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d --build "$@"
            wait_for_services
            check_health
            ;;
        "down")
            log_info "Stopping services..."
            podman-compose -f $COMPOSE_FILE -p $PROJECT_NAME down "$@"
            ;;
        "logs")
            if [ $# -gt 0 ]; then
                podman-compose -f $COMPOSE_FILE -p $PROJECT_NAME logs "$@"
            else
                podman-compose -f $COMPOSE_FILE -p $PROJECT_NAME logs
            fi
            ;;
        "build")
            check_dependencies
            validate_config
            log_info "Building services..."
            podman-compose -f $COMPOSE_FILE -p $PROJECT_NAME build "$@"
            ;;
        "clean")
            log_info "Cleaning up containers and volumes..."
            podman-compose -f $COMPOSE_FILE -p $PROJECT_NAME down --volumes "$@"
            podman system prune -f
            ;;
        "status")
            log_info "Service status:"
            podman-compose -f $COMPOSE_FILE -p $PROJECT_NAME ps
            ;;
        "health")
            check_health
            ;;
        "resources")
            show_resources
            ;;
        "update")
            update_images
            ;;
        "start")
            if [ $# -eq 0 ]; then
                log_error "Please specify a service to start"
                exit 1
            fi
            manage_service start "$1"
            ;;
        "stop")
            if [ $# -eq 0 ]; then
                log_error "Please specify a service to stop"
                exit 1
            fi
            manage_service stop "$1"
            ;;
        "restart")
            if [ $# -eq 0 ]; then
                log_error "Please specify a service to restart"
                exit 1
            fi
            manage_service restart "$1"
            ;;
        "service-logs")
            if [ $# -eq 0 ]; then
                log_error "Please specify a service"
                exit 1
            fi
            manage_service logs "$1"
            ;;
        *)
            echo "Usage: $0 {up|up-d|down|logs|build|clean|status|health|resources|update|start|stop|restart|service-logs} [service]"
            echo ""
            echo "Commands:"
            echo "  up [service]      - Start services (foreground)"
            echo "  up-d [service]    - Start services (background)"
            echo "  down [service]    - Stop services"
            echo "  logs [service]    - Show logs (optionally for specific service)"
            echo "  build [service]   - Build services"
            echo "  clean             - Clean up containers and volumes"
            echo "  status            - Show service status"
            echo "  health            - Check service health"
            echo "  resources         - Show resource usage"
            echo "  update            - Pull latest images"
            echo "  start <service>   - Start specific service"
            echo "  stop <service>    - Stop specific service"
            echo "  restart <service> - Restart specific service"
            echo "  service-logs <service> - Show logs for specific service"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"