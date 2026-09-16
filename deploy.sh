#!/bin/bash

# deploy.sh - Deployment script for Libretto
# Replaces Docker setup by creating virtual environment and running services natively

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
VENV_DIR="venv"
PYTHON_CMD="python3"
REDIS_PORT=6379
SERVER_PORT=8000
LOG_DIR="logs"
ENV_FILE=".env"  # Default environment file

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check system requirements
check_requirements() {
    print_status "Checking system requirements..."

    # Check Python 3
    if ! command_exists python3; then
        print_error "Python 3 is required but not installed. Please install Python 3.10 or higher."
        exit 1
    fi

    # Check Python version
    python_version=$(python3 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))")
    min_version="3.10"
    if [ "$(printf '%s\n' "$min_version" "$python_version" | sort -V | head -n1)" != "$min_version" ]; then
        print_error "Python $python_version found, but Python $min_version or higher is required."
        exit 1
    fi

    # Check Node.js
    if ! command_exists node; then
        print_error "Node.js is required but not installed. Please install Node.js 18 or higher."
        exit 1
    fi

    # Check npm
    if ! command_exists npm; then
        print_error "npm is required but not installed. Please install npm."
        exit 1
    fi

    # Check git (required for some Python dependencies)
    if ! command_exists git; then
        print_error "git is required but not installed. Please install git."
        exit 1
    fi

    # Check if redis-server is available (optional - we'll try to install if not)
    if ! command_exists redis-server; then
        print_warning "Redis server not found. Will attempt to install Redis."
        INSTALL_REDIS=true
    else
        INSTALL_REDIS=false
    fi

    print_success "System requirements check completed"
}

# Function to install Redis (Linux-specific)
install_redis() {
    if [ "$INSTALL_REDIS" = true ]; then
        print_status "Installing Redis server..."

        # Detect Linux distribution
        if command_exists apt-get; then
            # Ubuntu/Debian
            sudo apt-get update
            sudo apt-get install -y redis-server
        elif command_exists yum; then
            # CentOS/RHEL/Amazon Linux
            sudo yum install -y epel-release
            sudo yum install -y redis
        elif command_exists dnf; then
            # Fedora
            sudo dnf install -y redis
        elif command_exists pacman; then
            # Arch Linux
            sudo pacman -S --noconfirm redis
        else
            print_error "Could not detect package manager. Please install Redis manually."
            print_error "Visit: https://redis.io/docs/install/install-redis/"
            exit 1
        fi

        print_success "Redis installed successfully"
    fi
}

# Function to create virtual environment
create_venv() {
    print_status "Creating Python virtual environment..."

    if [ -d "$VENV_DIR" ]; then
        print_warning "Virtual environment already exists. Removing and recreating..."
        rm -rf "$VENV_DIR"
    fi

    $PYTHON_CMD -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"

    # Upgrade pip
    pip install --upgrade pip

    print_success "Virtual environment created and activated"
}

# Function to install Python dependencies
install_python_deps() {
    print_status "Installing Python dependencies..."

    # Ensure we're in the virtual environment
    source "$VENV_DIR/bin/activate"

    # Install server dependencies
    print_status "Installing dependencies..."
    pip install -r requirements.txt

    # Install shared libretto package
    print_status "Installing shared libretto package..."
    pip install -e .

    print_success "Python dependencies installed successfully"
}

# Function to build frontend
build_frontend() {
    print_status "Building frontend..."

    cd server/frontend

    # Install npm dependencies
    print_status "Installing npm dependencies..."
    npm install

    # Build the frontend
    print_status "Building SvelteKit frontend..."
    npm run build

    cd ../..

    print_success "Frontend built successfully"
}

# Function to create log directory
create_log_dir() {
    if [ ! -d "$LOG_DIR" ]; then
        mkdir -p "$LOG_DIR"
        print_status "Created log directory: $LOG_DIR"
    fi
}

# Function to start Redis server
start_redis() {
    print_status "Starting Redis server..."

    # Check if Redis is already running
    if lsof -Pi :$REDIS_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_warning "Redis is already running on port $REDIS_PORT"
        return 0
    fi

    # Start Redis in background
    redis-server --port $REDIS_PORT --daemonize yes --logfile "$LOG_DIR/redis.log"

    # Wait a moment and check if Redis started successfully
    sleep 2
    if lsof -Pi :$REDIS_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_success "Redis server started on port $REDIS_PORT"
    else
        print_error "Failed to start Redis server"
        exit 1
    fi
}

# Function to start the worker
start_worker() {
    print_status "Starting extraction worker..."

    # Ensure we're in the virtual environment
    source "$VENV_DIR/bin/activate"

    # Set default number of workers if not specified
    WORKERS=${WORKERS:-2}

    # Start worker in background
    nohup python -m worker --workers $WORKERS >> "$LOG_DIR/worker.log" 2>&1 &
    WORKER_PID=$!
    echo $WORKER_PID > "$LOG_DIR/worker.pid"

    print_success "Worker started with PID $WORKER_PID (workers: $WORKERS)"
}

# Function to start the server
start_server() {
    print_status "Starting FastAPI server..."

    # Check if server port is already in use
    if lsof -Pi :$SERVER_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_warning "Port $SERVER_PORT is already in use"
        print_error "Please stop the service using port $SERVER_PORT or change SERVER_PORT in this script"
        exit 1
    fi

    # Ensure we're in the virtual environment
    source "$VENV_DIR/bin/activate"

    # Start server in background
    nohup gunicorn server.app:app --config gunicorn.conf.py &
    SERVER_PID=$!
    echo $SERVER_PID > "$LOG_DIR/server.pid"

    # Wait a moment and check if server started successfully
    sleep 3
    if lsof -Pi :$SERVER_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_success "Server started with PID $SERVER_PID on port $SERVER_PORT"
    else
        print_error "Failed to start server. Check $LOG_DIR/server.log for details"
        exit 1
    fi
}

# Function to display status
show_status() {
    echo
    echo "========================================"
    echo "           DEPLOYMENT STATUS"
    echo "========================================"
    echo

    # Check Redis
    if lsof -Pi :$REDIS_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_success "Redis server: Running (port $REDIS_PORT)"
    else
        print_error "Redis server: Not running"
    fi

    # Check Server
    if lsof -Pi :$SERVER_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_success "FastAPI server: Running (port $SERVER_PORT)"
        echo "                Web interface: http://localhost:$SERVER_PORT"
    else
        print_error "FastAPI server: Not running"
    fi

    # Check Worker
    if [ -f "$LOG_DIR/worker.pid" ] && kill -0 $(cat "$LOG_DIR/worker.pid") 2>/dev/null; then
        WORKER_PID=$(cat "$LOG_DIR/worker.pid")
        print_success "Extraction worker: Running (PID $WORKER_PID)"
    else
        print_error "Extraction worker: Not running"
    fi

    echo
    echo "Logs are available in the '$LOG_DIR' directory:"
    echo "  - Redis: $LOG_DIR/redis.log"
    echo "  - Server: $LOG_DIR/server.log"
    echo "  - Worker: $LOG_DIR/worker.log"
    echo
    echo "To stop services, run: ./deploy.sh stop"
    echo "========================================"
}

# Function to stop services
stop_services() {
    print_status "Stopping services..."

    # Stop worker
    if [ -f "$LOG_DIR/worker.pid" ]; then
        WORKER_PID=$(cat "$LOG_DIR/worker.pid")
        if kill -0 $WORKER_PID 2>/dev/null; then
            kill $WORKER_PID
            rm -f "$LOG_DIR/worker.pid"
            print_success "Worker stopped"
        fi
    fi

    # Stop server
    if [ -f "$LOG_DIR/server.pid" ]; then
        SERVER_PID=$(cat "$LOG_DIR/server.pid")
        if kill -0 $SERVER_PID 2>/dev/null; then
            kill $SERVER_PID
            rm -f "$LOG_DIR/server.pid"
            print_success "Server stopped"
        fi
    fi

    # Stop Redis (only if we started it)
    if command_exists redis-cli; then
        redis-cli -p $REDIS_PORT shutdown nosave 2>/dev/null || true
        print_success "Redis stopped"
    fi

    print_success "All services stopped"
}

# Function to check environment file
check_env_file() {
    if [ ! -f "$ENV_FILE" ]; then
        if [ -f ".env.example" ]; then
            print_warning "No $ENV_FILE file found. Copying from .env.example"
            cp .env.example "$ENV_FILE"
            print_warning "Please edit $ENV_FILE file with your configuration before proceeding"
            print_warning "Key settings to configure:"
            print_warning "  - Database connections"
            print_warning "  - LLM API credentials"
            print_warning "  - Redis settings (if different from defaults)"
            read -p "Press Enter when you've configured the $ENV_FILE file..."
        else
            print_error "No $ENV_FILE or .env.example file found. Please create a $ENV_FILE file with required configuration."
            exit 1
        fi
    fi
    set -a; source "$ENV_FILE"; set +a
}

# Main function
main() {
    echo "========================================"
    echo "              Libretto"
    echo "========================================"
    echo

    # Parse command line arguments
    COMMAND="start"  # Default command

    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--env)
                ENV_FILE="$2"
                shift 2
                ;;
            stop|status|start)
                COMMAND="$1"
                shift
                ;;
            -h|--help)
                echo "Usage: $0 [COMMAND] [OPTIONS]"
                echo ""
                echo "Commands:"
                echo "  start   - Deploy and start services (default)"
                echo "  stop    - Stop all services"
                echo "  status  - Show current status"
                echo ""
                echo "Options:"
                echo "  -e, --env FILE    - Use specified environment file (default: .env)"
                echo "  -h, --help        - Show this help message"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Use '$0 --help' for usage information"
                exit 1
                ;;
        esac
    done

    # Handle commands
    case "$COMMAND" in
        "stop")
            stop_services
            exit 0
            ;;
        "status")
            show_status
            exit 0
            ;;
        "start")
            # Continue with deployment
            ;;
        *)
            print_error "Unknown command: $COMMAND"
            echo "Use '$0 --help' for usage information"
            exit 1
            ;;
    esac

    # Check if we're in the right directory
    if [ ! -f "docker-compose.yml" ] || [ ! -f "server/requirements.txt" ] || [ ! -f "worker/requirements.txt" ]; then
        print_error "Please run this script from the project root directory"
        exit 1
    fi

    check_env_file
    check_requirements
    install_redis
    create_venv
    install_python_deps
    build_frontend
    create_log_dir

    print_status "Starting services..."
    start_redis
    start_worker
    start_server

    show_status

    print_success "Deployment completed successfully!"
}

# Trap to ensure cleanup on exit
trap 'echo; print_warning "Deployment interrupted"' INT

# Run main function
main "$@"