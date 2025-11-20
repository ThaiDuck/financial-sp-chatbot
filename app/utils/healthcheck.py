#!/usr/bin/env python3
"""
Simple healthcheck script for supervisor to use.
"""
import requests
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_api_health():
    """Check if the API is healthy by calling the health endpoint"""
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            logger.info("API health check passed")
            return True
        else:
            logger.error(f"API health check failed with status code: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"API health check failed with error: {e}")
        return False

if __name__ == "__main__":
    healthy = check_api_health()
    sys.exit(0 if healthy else 1)
