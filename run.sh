#!/bin/bash

# Docker-based startup script for the multi-service API
# This script provides an easy way to manage the services with Docker

set -euo pipefail  # Exit on error, undefined vars, and pipe failures

# Configuration
COMPOSE_FILE="docker-compose.yml"
PROJECT_NAME="applite-xtrac"
# Set default port if not already defined
APPLITEXTRAC_PORT=${APPLITEXTRAC_PORT:-8369}
APPLITEXTRAC_HTTP_TIMEOUT=${APPLITEXTRAC_HTTP_TIMEOUT:-0}
REQUIRED_PORTS=(${APPLITEXTRAC_PORT} 4000)  # Ports that need to be available
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
    if timeout 10 curl -s -f http://localhost:${APPLITEXTRAC_PORT}/ping >/dev/null 2>&1; then
        log_success "Proxy service is responding"
        
        # Check individual services via proxy
        if timeout 10 curl -s -f http://localhost:${APPLITEXTRAC_PORT}/ping-all >/dev/null 2>&1; then
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
            # Shift past action and service to get additional arguments
            shift 2
            local log_args=""
            # Process additional arguments for docker-compose logs
            while [[ $# -gt 0 ]]; do
                case $1 in
                    --tail)
                        log_args="$log_args --tail $2"
                        shift 2
                        ;;
                    -f|--follow)
                        log_args="$log_args -f"
                        shift
                        ;;
                    -t|--timestamps)
                        log_args="$log_args -t"
                        shift
                        ;;
                    --since)
                        log_args="$log_args --since $2"
                        shift 2
                        ;;
                    --until)
                        log_args="$log_args --until $2"
                        shift 2
                        ;;
                    *)
                        log_error "Unknown logs option: $1"
                        log_info "Supported options: --tail N, -f/--follow, -t/--timestamps, --since TIME, --until TIME"
                        exit 1
                        ;;
                esac
            done
            
            # Default to follow if no specific options provided
            if [ -z "$log_args" ]; then
                log_args="-f"
            fi
            
            log_info "Getting logs for service: $service with options: $log_args"
            docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME logs $log_args $service || log_error "Failed to get logs for service $service"
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
    
    # Check ports (exclude proxy port ${APPLITEXTRAC_PORT} since it will run locally)
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
    
    # Set environment variables for local development with network optimizations
    export APPLITEXTRAC_PORT  # Export the port variable
    export UNSTRUCTURED_IO_URL="http://localhost:8000"
    export LIBREOFFICE_URL="http://localhost:2004" 
    export PANDOC_URL="http://localhost:3030"
    export GOTENBERG_URL="http://localhost:3001"
    
    # Network optimization environment variables for Docker communication
    export HTTPX_CONNECT_TIMEOUT="5.0"    # Faster connection timeout
    export HTTPX_POOL_TIMEOUT="3.0"       # Faster pool timeout
    export DISABLE_IPV6="true"            # Force IPv4 only to avoid DNS conflicts
    export DOCKER_NETWORK_MODE="bridge"   # Explicit bridge mode
    
    log_info "Starting proxy service locally on port ${APPLITEXTRAC_PORT:-8369}..."
    log_info "Press Ctrl+C to stop"
    
    # Start with auto-reload for development
    uvicorn app:app --host 0.0.0.0 --port ${APPLITEXTRAC_PORT} --reload --reload-exclude 'venv/'
}

# Stop development mode
stop_dev_mode() {
    log_info "Stopping development mode..."
    
    # Stop containerized services
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME down \
        unstructured-io libreoffice pandoc gotenberg || log_warning "Failed to stop containerized services"
    
    # Kill local proxy process with graceful shutdown first, then force kill
    # Try multiple patterns to find uvicorn processes
    local proxy_pids=$(pgrep -f "uvicorn.*app:app.*${APPLITEXTRAC_PORT}" || pgrep -f "uvicorn.*convert.*app:app" || pgrep -f "uvicorn.*--port ${APPLITEXTRAC_PORT}" || true)
    
    if [ -n "$proxy_pids" ]; then
        log_info "Found proxy service processes: $proxy_pids"
        
        # Kill all found processes
        for proxy_pid in $proxy_pids; do
            if kill -0 $proxy_pid 2>/dev/null; then
                log_info "Stopping proxy service (PID: $proxy_pid)"
                
                # Try graceful shutdown first
                kill $proxy_pid 2>/dev/null || true
                
                # Wait up to 5 seconds for graceful shutdown
                local count=0
                while [ $count -lt 5 ] && kill -0 $proxy_pid 2>/dev/null; do
                    sleep 1
                    count=$((count + 1))
                done
                
                # If still running, force kill with SIGKILL
                if kill -0 $proxy_pid 2>/dev/null; then
                    log_warning "Proxy service (PID: $proxy_pid) didn't stop gracefully, force killing..."
                    kill -9 $proxy_pid 2>/dev/null || true
                    
                    # Wait a moment for the kill to take effect
                    sleep 1
                    
                    # Check if it's finally dead
                    if kill -0 $proxy_pid 2>/dev/null; then
                        log_error "Failed to kill proxy service (PID: $proxy_pid)"
                    else
                        log_success "Proxy service (PID: $proxy_pid) force killed successfully"
                    fi
                else
                    log_success "Proxy service (PID: $proxy_pid) stopped gracefully"
                fi
            fi
        done
    else
        log_info "No proxy service processes found"
    fi
    
    log_success "Development mode stopped"
}

# Helper functions for common operations
do_start() {
    local background=${1:-false}
    shift  # Remove the background flag from arguments
    
    check_dependencies
    validate_config
    check_ports
    
    if $background; then
        log_info "Starting services in background with Docker..."
    else
        log_info "Starting services with Docker..."
    fi
    
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d --build "$@" || log_error "Failed to start services"
    wait_for_services
    check_health
}

do_stop() {
    log_info "Stopping services..."
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME down "$@" || log_warning "Failed to stop services"
}

do_health() {
    check_health
}

do_build() {
    check_dependencies
    validate_config
    
    log_info "Building Docker images..."
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME build "$@" || log_error "Failed to build Docker images"
    log_success "Docker images built successfully"
}

# Run tests
run_tests() {
    local test_type=${1:-"all"}
    
    case $test_type in
        "all")
            log_info "Running all tests..."
            run_all_tests
            ;;
        "conversion")
            log_info "Running conversion tests..."
            run_conversion_tests
            ;;
        "url")
            log_info "Running URL tests..."
            run_url_tests
            ;;
        *)
            log_error "Unknown test type: $test_type"
            log_info "Available test types: all, conversion, url"
            exit 1
            ;;
    esac
}

# Run all tests
run_all_tests() {
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
        pip install -r requirements-dev.txt
    else
        source venv/bin/activate
        # Check if pytest is available, install dev requirements if not
        if ! ./venv/bin/python -c "import pytest" 2>/dev/null; then
            log_info "Installing development dependencies..."
            pip install -r requirements-dev.txt
        fi
    fi
    
    log_info "Running all tests..."
    
    # Run pytest with coverage
    if ./venv/bin/python -c "import pytest" 2>/dev/null; then
        ./venv/bin/python -m pytest --tb=short --cov=convert --cov-report=html:htmlcov || log_error "Tests failed"
    else
        log_warning "pytest not found in virtual environment, running basic Python tests..."
        ./venv/bin/python -m unittest discover tests/ -v || log_error "Basic tests failed"
    fi
    
    log_success "All tests completed"
}

# Run conversion tests specifically
run_conversion_tests() {
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
        pip install -r requirements-dev.txt
    else
        source venv/bin/activate
        # Check if pytest is available, install dev requirements if not
        if ! ./venv/bin/python -c "import pytest" 2>/dev/null; then
            log_info "Installing development dependencies..."
            pip install -r requirements-dev.txt
        fi
    fi
    
    log_info "Running conversion integration tests with detailed output..."
    
    # Run the specific test method that shows all conversion results
    if ./venv/bin/python -c "import pytest" 2>/dev/null; then
        ./venv/bin/python -m pytest tests/integration/test_conversions.py::TestConversionEndpoints::test_all_file_conversions -v -s --tb=short || log_error "Conversion tests failed"
    else
        log_warning "pytest not found in virtual environment, running basic Python tests..."
        ./venv/bin/python -m unittest tests.integration.test_conversions.TestConversionEndpoints.test_all_file_conversions -v || log_error "Basic conversion tests failed"
    fi
    
    log_success "Conversion tests completed"
}

# Run URL tests specifically
run_url_tests() {
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
        pip install -r requirements-dev.txt
    else
        source venv/bin/activate
        # Check if pytest is available, install dev requirements if not
        if ! ./venv/bin/python -c "import pytest" 2>/dev/null; then
            log_info "Installing development dependencies..."
            pip install -r requirements-dev.txt
        fi
    fi
    
    log_info "Running URL fetching tests..."
    
    # Run the URL fetching tests
    if ./venv/bin/python -c "import pytest" 2>/dev/null; then
        ./venv/bin/python -m pytest convert/test_url_fetching.py -v -s --tb=short || log_error "URL tests failed"
    else
        log_warning "pytest not found in virtual environment, running basic Python tests..."
        ./venv/bin/python -m unittest convert.test_url_fetching -v || log_error "Basic URL tests failed"
    fi
    
    log_success "URL tests completed"
}

# Check and activate Python virtual environment
check_and_activate_venv() {
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
    
    cd - > /dev/null
}

# Main command processing
main() {
    # Check and activate venv for all commands
    check_and_activate_venv
    
    local command=$1
    shift
    
    case "$command" in
        "activate")
            log_success "Virtual environment is active"
            ;;
        "up"|"start")
            do_start false "$@"
            ;;
        "up-d"|"start:d")
            do_start true "$@"
            ;;
        "down"|"stop")
            do_stop "$@"
            ;;
        "build")
            do_build "$@"
            ;;
        "status"|"ps"|"health")
            do_health
            ;;
        "logs")
            if [ $# -eq 0 ]; then
                log_error "No service specified for logs"
                log_info "Usage: $0 logs <service> [tail options]"
                log_info "Examples:"
                log_info "  $0 logs gotenberg              # Follow logs (default)"
                log_info "  $0 logs gotenberg --tail 50     # Show last 50 lines"
                log_info "  $0 logs gotenberg --tail 100 -f # Show last 100 lines and follow"
                exit 1
            fi
            
            local service=$1
            shift
            manage_service logs $service "$@"
            ;;
        "restart")
            log_info "Restarting all services..."
            do_stop "$@"
            do_start false "$@"
            ;;
        "restartd")
            log_info "Restarting all services daemons..."
            do_stop "$@"
            do_start true "$@"
            ;;
        "dev")
            dev_mode
            ;;
        "dev:stop")
            stop_dev_mode
            ;;
        "test")
            run_tests "all"
            ;;
        "test:conversion")
            run_tests "conversion"
            ;;
        "test:url")
            run_tests "url"
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
            echo "Usage: $0 {activate|up|down|stop|start|start:d|status|ps|logs|restart|build|dev|dev:stop|update|resources|health|test|test:conversion|test:url}"
            echo ""
            echo "Commands:"
            echo "  activate     Check and activate Python virtual environment"
            echo "  start|up     Start all services"
            echo "  startd|up-d  Start all services in background"
            echo "  stop|down    Stop all services"
            echo "  build        Build Docker images"
            echo "  logs <svc> [opts]   Show logs for a specific service (supports --tail, -f, -t, --since, --until)"
            echo "  restart      Restart all services"
            echo "  dev          Start development mode (containers + local proxy)"
            echo "  dev:stop     Stop development mode"
            echo "  update       Pull latest Docker images"
            echo "  resources    Show container resource usage"
            echo "  status|health|ps   Check service health"
            echo "  test         Run all tests"
            echo "  test:conversion    Run conversion integration tests"
            echo "  test:url           Run URL fetching tests"
            exit 1
            ;;
    esac
}


# Execute the main function with all script arguments
main "$@"