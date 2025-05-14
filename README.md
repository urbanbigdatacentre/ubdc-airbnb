# UBDC Airbnb Data Collection System

## Overview

The UBDC Airbnb Data Collection System is a containerized application designed to scrape Airbnb data from user-defined geographic areas continuously. Built for researchers and data analysts, it enables large-scale data collection with robust scalability options.

**Key Features:**
- Geographic-based data collection using Areas of Interest (AOIs)
- Continuous harvesting of listing details and calendar availability
- Scalable deployment via Docker or Docker Swarm
- Django and Celery-powered task processing architecture

## Quick Start Guide

### Prerequisites
- Docker and Docker Compose
- Git
- Basic understanding of command-line interfaces

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/ubdc-airbnb.git
   cd ubdc-airbnb
   ```

2. **Build the Docker image**
   ```bash
   make build-image
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env file to set required configuration values
   ```

4. **Start the system**
   ```bash
   # Launch database, message broker, and worker
   docker compose -f docker/local-service.yml --profile all up
   ```

5. **Scale workers (optional)**
   ```bash
   # Increase number of workers to handle more concurrent tasks
   docker compose -f docker/local-service.yml --scale worker=3
   ```

## Data Collection Workflow

### 1. Define Areas of Interest

```bash
# Add a new geographic area to collect data from
python manage.py add-aoi --name "City Center" --geojson "path/to/geojson/file.geojson"
```
# List all configured areas
python manage.py list-aoi
```

### 2. Configure Collection Parameters

```bash
# Enable different collection activities for an area
python manage.py edit-aoi --aoi-id 1 --enable-discovery
python manage.py edit-aoi --aoi-id 1 --enable-calendar-harvest
python manage.py edit-aoi --aoi-id 1 --enable-listing-details
```

### 3. View and Extract Data

```bash
# View listings in an area
python manage.py print-listings --aoi-id 1

# Manually scrape specific listing data
python manage.py scrape-listing-data --listing-id 123456 --calendar
python manage.py scrape-listing-data --listing-id 123456 --details
```

## System Architecture

The system follows a service-oriented architecture with three core components:

### Core Components

1. **Database (PostgreSQL/PostGIS)**
   - Stores listing metadata, property details, and geographic information
   - Enables spatial queries and GIS integration

2. **Message Broker (RabbitMQ)**
   - Manages asynchronous task queuing
   - Enables scalable, distributed processing

3. **Application Layer**
   - **Django**: Handles data models, business logic, and management commands
   - **Celery**: Processes asynchronous tasks including:
     - Listing discovery
     - Property details collection
     - Calendar availability harvesting

### Worker Types

- **Scheduler**: Initiates and coordinates harvesting tasks (single instance)
- **Worker**: Executes data collection tasks and interacts with Airbnb API (horizontally scalable)

## Deployment Options

### Single-Host Deployment
Ideal for small to medium research projects:
- All components run on a single machine
- Uses Docker Compose for orchestration
- Supports multiple workers with a single scheduler

### Docker Swarm Deployment
For large-scale data collection operations:
- Distributed across multiple hosts
- Enhanced reliability and failover capabilities
- Production-ready configuration
- Horizontally scalable worker nodes

## Advanced Management Commands

Beyond the basic workflow, the system offers additional management commands for operation and monitoring:

### Area of Interest (AOI) Management
```bash
# Add AOI using latitude/longitude and radius
python manage.py add_aoi --name "City Center" --lat 55.9533 --lon -3.1883 --radius 2000

# Remove an AOI
python manage.py remove_aoi --aoi_id 1
```

### Harvesting Operations
```bash
# Initialize a new harvest operation
python manage.py init_harvest --aoi_id 1

# Start discovery of listings in an area
python manage.py discover_listings --aoi_id 1

# Gather details for a specific listing
python manage.py gather_details --listing_id 123456

# Collect calendar availability for a date range
python manage.py gather_calendar --listing_id 123456 --start_date 2024-01-01 --end_date 2024-12-31
```

### Monitoring and Management
```bash
# Check system status
python manage.py system_status

# Monitor active workers
python manage.py worker_status

# View harvest progress
python manage.py harvest_progress --aoi_id 1
```

## GIS Integration

All collected data is stored in a PostGIS-enabled database, allowing for:
- Spatial analysis and visualization in GIS applications like QGIS
- Custom PostgreSQL user-defined functions for specialized geospatial queries
- Integration with other spatial data sources

## Development Guide

### Environment Setup

This project uses modern Python development tools:
- Python 3.10+
- Poetry for dependency management
- Devcontainers for consistent development environments

### Getting Started with Development

1. Clone the repository
2. Open in an IDE with devcontainer support (e.g., VS Code)
3. Your IDE will prompt you to reopen the project in a devcontainer
4. Once connected, all dependencies will be automatically installed

>[!Note]
> Check the files in .devcontainer for more information regarding the embedded development environment. 


### Verifying Your Setup

Run the test suite to ensure everything is working properly:
```bash
make test
```

## Technical Requirements

- Container engine (Docker/Podman)
- PostgreSQL database with PostGIS extension
- RabbitMQ message broker
- Network connectivity for API access
