#!/bin/bash

# Performance test script for the proxy service in dev mode

echo "=== Performance Test for Proxy Service ==="
echo "Testing response times for various endpoints..."
echo

# Test basic health endpoint
echo "1. Testing /ping endpoint:"
time curl -s -o /dev/null -w "HTTP %{http_code}, Time: %{time_total}s\n" http://localhost:8369/ping
echo

# Test supported conversions endpoint
echo "2. Testing /convert/supported endpoint:"
time curl -s -o /dev/null -w "HTTP %{http_code}, Time: %{time_total}s\n" http://localhost:8369/convert/supported
echo

# Test a simple conversion endpoint (without actual file)
echo "3. Testing /convert/docx-pdf endpoint (error expected, but should be fast):"
time curl -s -o /dev/null -w "HTTP %{http_code}, Time: %{time_total}s\n" \
  -F "file=@/dev/null" \
  http://localhost:8369/convert/docx-pdf 2>/dev/null || echo "Expected error - no file provided"
echo

echo "=== Performance Test Complete ==="
echo "If response times are still slow (>5s), check:"
echo "- Docker container resource limits"
echo "- Network connectivity to containers"
echo "- Service health (docker-compose ps)"
echo "- Container logs (docker-compose logs)"
