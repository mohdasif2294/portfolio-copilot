#!/bin/bash
# Setup Qdrant vector database using Docker

CONTAINER_NAME="portfolio-copilot-qdrant"
DATA_PATH="$(dirname "$0")/../data/vector_store"

# Create data directory if it doesn't exist
mkdir -p "$DATA_PATH"

# Check if container already exists
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Container $CONTAINER_NAME already exists."

    # Check if it's running
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Qdrant is already running on http://localhost:6333"
    else
        echo "Starting existing container..."
        docker start "$CONTAINER_NAME"
        echo "Qdrant started on http://localhost:6333"
    fi
else
    echo "Creating and starting Qdrant container..."
    docker run -d \
        --name "$CONTAINER_NAME" \
        -p 6333:6333 \
        -p 6334:6334 \
        -v "$DATA_PATH:/qdrant/storage" \
        qdrant/qdrant

    echo "Qdrant started on http://localhost:6333"
    echo "Dashboard available at http://localhost:6333/dashboard"
fi
