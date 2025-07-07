#!/bin/bash
# Startup script for the Agentic Specbook Framework
# Handles PostgreSQL conflicts and service management

set -e

echo "🚀 Starting Agentic Specbook Framework..."

# Check if local PostgreSQL is running and offer to stop it
if brew services list | grep -q "postgresql@14.*started"; then
    echo "⚠️  Local PostgreSQL is running on port 5432"
    echo "This will conflict with the Docker PostgreSQL container."
    echo ""
    read -p "Stop local PostgreSQL temporarily? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🛑 Stopping local PostgreSQL..."
        brew services stop postgresql@14
        LOCAL_PG_STOPPED=true
    else
        echo "❌ Cannot start with PostgreSQL conflict. Exiting."
        exit 1
    fi
fi

# Ensure Docker services are running
echo "🐳 Starting Docker services..."
docker-compose up -d postgres redis

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
while ! docker-compose exec -T postgres pg_isready -U postgres -d bluegem > /dev/null 2>&1; do
    echo "   Waiting for PostgreSQL..."
    sleep 2
done

while ! docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; do
    echo "   Waiting for Redis..."
    sleep 1
done

echo "✅ Services are ready!"

# Run validation tests
echo "🧪 Running validation tests..."
if python test_setup.py > /dev/null 2>&1; then
    echo "✅ All tests passed!"
else
    echo "❌ Some tests failed. Check setup."
    exit 1
fi

# Cleanup function
cleanup() {
    echo ""
    echo "🛑 Shutting down..."
    
    # Restart local PostgreSQL if we stopped it
    if [ "$LOCAL_PG_STOPPED" = true ]; then
        echo "🔄 Restarting local PostgreSQL..."
        brew services start postgresql@14
    fi
    
    echo "👋 Goodbye!"
    exit 0
}

# Set trap for cleanup
trap cleanup SIGINT SIGTERM

# Set environment variables explicitly
export DATABASE_URL="postgresql+asyncpg://postgres:password@localhost:5432/bluegem"
export REDIS_URL="redis://localhost:6379"

# Start the chat interface
echo "💬 Starting chat interface..."
echo "Press Ctrl+C to stop and cleanup"
echo ""

python -m cli.chat_interface chat

# If we get here, cleanup manually
cleanup