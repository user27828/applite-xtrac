#!/bin/bash

# Docker-based startup script for the multi-service API
# This script provides an easy way to manage the services with Docker

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
    
    if ! command -v docker &> /dev/null; then
        missing_deps+=("docker")
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        missing_deps+=("docker-compose")
    fi
    
    if ! command -v python &> /dev/null; then
        missing_deps+=("python")
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
    shift 2
    local services_to_check=("$@")
    
    # If no specific services provided, use all SERVICES
    if [ ${#services_to_check[@]} -eq 0 ]; then
        services_to_check=("${SERVICES[@]}")
    fi
    
    local elapsed=0
    
    log_info "Waiting for services to be ready..."
    
    while [ $elapsed -lt $timeout ]; do
        local all_healthy=true
        
        for service in "${services_to_check[@]}"; do
            if ! docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME ps $service 2>/dev/null | grep -q "Up"; then
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
    if timeout 10 curl -s -f http://localhost:8369/ping >/dev/null 2>&1; then
        log_success "Proxy service is responding"
        
        # Check individual services via proxy
        if timeout 10 curl -s -f http://localhost:8369/ping-all >/dev/null 2>&1; then
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
    docker stats --no-stream $(docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME ps -q) 2>/dev/null || log_warning "Could not retrieve container stats (timeout or no containers running)"
}

# Pull latest images
update_images() {
    log_info "Pulling latest images..."
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME pull || log_error "Failed to pull images"
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
            docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d $service || log_error "Failed to start service $service"
            ;;
        stop)
            log_info "Stopping service: $service"
            docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME stop $service || log_error "Failed to stop service $service"
            ;;
        restart)
            log_info "Restarting service: $service"
            docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME restart $service || log_error "Failed to restart service $service"
            ;;
        logs)
            timeout 30 docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME logs -f $service || log_error "Failed to get logs for service $service (timeout)"
            ;;
        *)
            log_error "Unknown action: $action"
            exit 1
            ;;
    esac
}

# Development mode - run proxy locally, others in containers
dev_mode() {
    log_info "Starting development mode..."
    
    # Check dependencies
    check_dependencies
    validate_config
    
    # Check ports (exclude proxy port 8369 since it will run locally)
    local dev_ports=(4000)  # Only check non-proxy ports
    for port in "${dev_ports[@]}"; do
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            log_error "Port $port already in use"
            exit 1
        fi
    done
    
    # Start all services except proxy
    log_info "Starting containerized services (excluding proxy)..."
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d --build \
        unstructured-io libreoffice pandoc gotenberg || log_error "Failed to start containerized services"
    
    # Wait for containerized services
    wait_for_services 60 5 unstructured-io libreoffice pandoc gotenberg
    
    # Check containerized services health
    check_dev_services_health
    
    # Start proxy service locally
    start_local_proxy
}

# Check health of containerized services only
check_dev_services_health() {
    log_info "Checking containerized services health..."
    
    # Check if containers are running
    for service in unstructured-io libreoffice pandoc gotenberg; do
        if ! docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME ps $service 2>/dev/null | grep -q "Up"; then
            log_error "Service $service is not running"
            return 1
        fi
    done
    
    log_success "Containerized services are running"
}

# Start proxy service locally
start_local_proxy() {
    local proxy_dir="proxy-service"
    
    if [ ! -d "$proxy_dir" ]; then
        log_error "Proxy service directory '$proxy_dir' not found"
        exit 1
    fi
    
    cd "$proxy_dir"
    
    # Check if Python environment exists
    if [ ! -d "venv" ]; then
        log_warning "Virtual environment not found. Creating one..."
        python3 -m venv venv
        source venv/bin/activate
        pip install -r requirements.txt
    else
        source venv/bin/activate
    fi
    
    # Set environment variables for local development
    export APPLITE_CONVERT_PORT=8369
    export UNSTRUCTURED_IO_URL="http://localhost:8000"
    export LIBREOFFICE_URL="http://localhost:3000" 
    export PANDOC_URL="http://localhost:3030"
    export GOTENBERG_URL="http://localhost:3001"
    
    log_info "Starting proxy service locally on port 8369..."
    log_info "Press Ctrl+C to stop"
    
    # Start with auto-reload for development
    uvicorn convert.main:app --host 0.0.0.0 --port 8369 --reload
}

# Stop development mode
stop_dev_mode() {
    log_info "Stopping development mode..."
    
    # Stop containerized services
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME down \
        unstructured-io libreoffice pandoc gotenberg || log_warning "Failed to stop containerized services"
    
    # Kill local proxy process
    local proxy_pid=$(pgrep -f "uvicorn.*convert.main:app")
    if [ -n "$proxy_pid" ]; then
        log_info "Stopping local proxy service (PID: $proxy_pid)"
        kill $proxy_pid
    fi
    
    log_success "Development mode stopped"
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
            log_info "Starting services with Docker..."
            docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d --build "$@" || log_error "Failed to start services"
            wait_for_services
            check_health
            ;;
        "up-d")
            check_dependencies
            validate_config
            check_ports
            log_info "Starting services in background with Docker..."
            docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d --build "$@" || log_error "Failed to start services"
            wait_for_services
            check_health
            ;;
        "down")
            log_info "Stopping services..."
            docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME down "$@" || log_warning "Failed to stop services"
            ;;
        "logs")
            if [ $# -eq 0 ]; then
                log_error "No service specified for logs"
                log_info "Usage: $0 logs <service>"
                exit 1
            fi
            
            local service=$1
            manage_service logs $service
            ;;
        "restart")
            log_info "Restarting all services..."
            docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME restart || log_warning "Failed to restart services"
            ;;
        "dev")
            dev_mode
            ;;
        "stop-dev")
            stop_dev_mode
            ;;
        "update")
            update_images
            ;;
        "resources")
            show_resources
            ;;
        "health")
            check_health
            ;;
        *)
            log_error "Unknown command: $command"
            echo "Usage: $0 {up|down|logs|restart|dev|stop-dev|update|resources|health}"
            exit 1
            ;;
    esac
}

# Execute the main function with all script arguments
main "$@"