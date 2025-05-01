#!/bin/bash

echo "Starting services with docker-compose..."
docker compose up -d --build

echo "Waiting for services to initialize..."
sleep 5

echo "API documentation should be available at: http://localhost:8000/docs" 