#!/bin/bash

# Activate virtual environment if it exists
if [ -d "python3-virtualenv" ]; then
  source python3-virtualenv/bin/activate
  echo "Activated python3-virtualenv"
elif [ -d ".venv" ]; then
  source .venv/bin/activate
  echo "Activated .venv"
else
  echo "No virtual environment found, running tests with system Python"
fi

# Set testing environment variable
export TESTING=true

# Run the tests
echo "Running tests..."
python -m unittest discover -s tests -v

# Check if tests passed
if [ $? -eq 0 ]; then
  echo "All tests passed!"
else
  echo "Some tests failed!"
fi

# Print completion message
echo "Tests completed!"
