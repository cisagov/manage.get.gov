#!/bin/bash
set -e

echo "Simulating CI OWASP scan locally..."
echo ""

# Clean up any previous runs
echo "Cleaning up..."
docker compose down
git checkout registrar/config/settings.py 2>/dev/null || true

# Inject MockUserLogin (exactly like CI does)
echo "Injecting MockUserLogin middleware..."
perl -pi \
  -e 's/"django.contrib.auth.middleware.AuthenticationMiddleware",/$&"registrar.tests.common.MockUserLogin",/' \
  registrar/config/settings.py

# Verify the injection worked
echo "Verifying injection..."
if grep -q "MockUserLogin" registrar/config/settings.py; then
    echo "MockUserLogin injected successfully"
else
    echo "MockUserLogin injection failed!"
    exit 1
fi

# Start services
echo "Starting services..."
docker compose up -d app db

# Wait for app to be ready
echo "Waiting for app to be ready..."
sleep 10

# Run OWASP scan (exactly like CI does)
echo "Running OWASP scan..."
docker compose run owasp

# Capture exit code
EXIT_CODE=$?

# Cleanup
echo "Cleaning up..."
git checkout registrar/config/settings.py
docker compose down

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "OWASP scan PASSED (exit code: $EXIT_CODE)"
else
    echo "OWASP scan FAILED (exit code: $EXIT_CODE)"
fi

exit $EXIT_CODE