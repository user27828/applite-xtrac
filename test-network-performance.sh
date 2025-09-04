#!/bin/bash

# Network Performance Test Script for Dev Mode
# This script tests the network performance between the local proxy and containerized services

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROXY_URL="http://localhost:8369"
TEST_ITERATIONS=5
TIMEOUT=30

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

# Test basic connectivity
test_connectivity() {
    log_info "Testing basic connectivity to proxy service..."
    if curl -s --max-time 5 "${PROXY_URL}/ping" > /dev/null 2>&1; then
        log_success "Proxy service is responding"
        return 0
    else
        log_error "Proxy service is not responding"
        return 1
    fi
}

# Test service endpoints with timing
test_endpoint() {
    local endpoint=$1
    local description=$2
    local times=()

    log_info "Testing ${description} (${TEST_ITERATIONS} iterations)..."

    for i in $(seq 1 $TEST_ITERATIONS); do
        local start_time=$(date +%s.%3N)
        if curl -s --max-time $TIMEOUT -w "%{http_code}" "${PROXY_URL}${endpoint}" > /dev/null 2>&1; then
            local end_time=$(date +%s.%3N)
            local duration=$(echo "$end_time - $start_time" | bc 2>/dev/null || echo "0")
            times+=($duration)
            echo "  Iteration $i: ${duration}s"
        else
            log_warning "  Iteration $i: Failed or timeout"
            times+=(999)
        fi
        sleep 0.5  # Brief pause between requests
    done

    # Calculate statistics
    local valid_times=()
    for time in "${times[@]}"; do
        if (( $(echo "$time < 999" | bc -l 2>/dev/null || echo "0") )); then
            valid_times+=($time)
        fi
    done

    if [ ${#valid_times[@]} -gt 0 ]; then
        local min_time=$(printf '%s\n' "${valid_times[@]}" | sort -n | head -n1)
        local max_time=$(printf '%s\n' "${valid_times[@]}" | sort -n | tail -n1)
        local sum=0
        for time in "${valid_times[@]}"; do
            sum=$(echo "$sum + $time" | bc 2>/dev/null || echo "$sum")
        done
        local avg_time=$(echo "scale=3; $sum / ${#valid_times[@]}" | bc 2>/dev/null || echo "0")

        log_success "${description} - Min: ${min_time}s, Max: ${max_time}s, Avg: ${avg_time}s"
    else
        log_error "${description} - All requests failed"
    fi
}

# Test Docker network connectivity
test_docker_network() {
    log_info "Testing Docker network connectivity..."

    # Check if containers are running
    local containers=("applite-convert-unstructured-io-1" "applite-convert-libreoffice-1" "applite-convert-pandoc-1" "applite-convert-gotenberg-1")

    for container in "${containers[@]}"; do
        if docker ps --format "table {{.Names}}" | grep -q "^${container}$"; then
            log_success "Container ${container} is running"
        else
            log_warning "Container ${container} is not running"
        fi
    done

    # Test direct container connectivity from host
    log_info "Testing direct container connectivity..."
    if docker run --rm --network applite-convert_app-network alpine wget -q --timeout=5 -O /dev/null http://applite-convert-unstructured-io-1:8000 2>/dev/null; then
        log_success "Container-to-container networking is working"
    else
        log_warning "Container-to-container networking may have issues"
    fi
}

# Main test function
main() {
    log_info "Starting Network Performance Test for Dev Mode"
    log_info "============================================"

    # Check if proxy is running
    if ! test_connectivity; then
        log_error "Cannot proceed with tests - proxy service not available"
        exit 1
    fi

    # Test Docker network
    test_docker_network

    # Test various endpoints
    test_endpoint "/ping" "Basic ping endpoint"
    test_endpoint "/ping-all" "Service health check"

    # Test conversion endpoints (if available)
    if curl -s --max-time 5 "${PROXY_URL}/convert/test" > /dev/null 2>&1; then
        test_endpoint "/convert/test" "Conversion test endpoint"
    fi

    log_info "============================================"
    log_success "Network performance test completed"
    log_info "If response times are still slow (>5s), consider:"
    log_info "  1. Checking Docker Desktop network settings"
    log_info "  2. Disabling IPv6 in Docker Desktop"
    log_info "  3. Restarting Docker Desktop"
    log_info "  4. Checking for VPN interference"
}

# Run main function
main "$@"
