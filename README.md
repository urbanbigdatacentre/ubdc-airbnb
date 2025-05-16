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
- Git
- Docker and Docker Compose
- Basic understanding of command-line interfaces
- (Optional) A dedicated postgreSQL/PostGIS database
- (Optional) A subscription to smart proxy service for IP rotation

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
   # Edit .env file and set the required values
   cp .env.example .env
   ```

4. **Start the system**
   ```bash
   # Launch database, message broker, and worker
   # the -d flag runs the containers in detached mode (background)
   docker compose -f docker-compose.yml -d --profile all up 
   ```

5. **(optional) Scale workers**
   ```bash
   # Increase number of workers to handle more concurrent tasks
   docker compose -f docker-compose.yml --scale worker=3
   ```

## Data Collection Workflow

### 1. Activate the Virtual Environment
```bash
# requires pipx
make install-env
```

### 2. Define Areas of Interest

```bash
# Add a new geographic area to collect data from
poetry run src/ubdc_airbnb/manage.py add-aoi --name "City Center" --geojson "path/to/geojson/file.geojson"
```
```bash
# List all configured areas
poetry run src/ubdc_airbnb/manage.py  list-aoi
```

### 3. Configure Collection Parameters

```bash
# Enable different collection activities for an area
poetry run src/ubdc_airbnb/manage.py  edit-aoi --aoi-id 1 --enable-discovery
poetry run src/ubdc_airbnb/manage.py  edit-aoi --aoi-id 1 --enable-calendar-harvest
poetry run src/ubdc_airbnb/manage.py  edit-aoi --aoi-id 1 --enable-listing-details
```

### 5.  Collect Data from an Area

```bash
# Discover any new listings in the discovery enabled areas
poetry run src/ubdc_airbnb/manage.py ./manage.py run-beat-job op_discover_new_listings_periodical
```

```bash
# Collected list-details for the listings in the `enable-listing-details` areas
poetry run src/ubdc_airbnb/manage.py ./manage.py run-beat-job op_collect_listing_details_periodical
```

```bash
# Collected calendar data for the listings in the `enable-calendar-harvest` areas
poetry run src/ubdc_airbnb/manage.py ./manage.py run-beat-job op_update_calendar_periodical
```

Alternatively, if you know if you know the listing ID of a listing you want to scrape, you can run the following commands:

```bash
# Manually scrape specific listing data
poetry run src/ubdc_airbnb/manage.py  scrape-listing-data --calendar --listing-id 123456 
poetry run src/ubdc_airbnb/manage.py  scrape-listing-data --details  --listing-id 123456 
```

>[!Warning]
> If you are not using a smart proxy service, you WILL be time-banned by Airbnb. 

>[!Note]
> if you have `beat` enabled, the above commands will be run automatically acording to the schedule defined

### 6. Extract Data

```bash
# Export the responses to a jsonnl file for further analysis
# you can use: 
# --only-latest: to only export the latest response (default) or
# --since: to export all responses since a given date
poetry run src/ubdc_airbnb/manage.py  export-data --details  --listing-id 123456 --output-file "details_listing_123456.jsonnl"
```

```bash
# same as above but for calendar data
poetry run src/ubdc_airbnb/manage.py  export-data --calendar --listing-id 123456 --output-file "calendar_listing_123456.jsonnl"
```
### 7. Delete an Area of Interest

```bash
poetry run src/ubdc_airbnb/manage.py  edit-aoi --aoi-id 1 --delete
```


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
poetry run src/ubdc_airbnb/manage.py  add_aoi --name "City Center" --lat 55.9533 --lon -3.1883 --radius 2000

# Remove an AOI
poetry run src/ubdc_airbnb/manage.py  remove_aoi --aoi_id 1
```

### Harvesting Operations
```bash
# Initialize a new harvest operation
poetry run src/ubdc_airbnb/manage.py  init_harvest --aoi_id 1

# Start discovery of listings in an area
poetry run src/ubdc_airbnb/manage.py  discover_listings --aoi_id 1

# Gather details for a specific listing
poetry run src/ubdc_airbnb/manage.py  gather_details --listing_id 123456

# Collect calendar availability for a date range
poetry run src/ubdc_airbnb/manage.py  gather_calendar --listing_id 123456 --start_date 2024-01-01 --end_date 2024-12-31
```

### Monitoring and Management
```bash
# Check system status
poetry run src/ubdc_airbnb/manage.py  system_status

# Monitor active workers
poetry run src/ubdc_airbnb/manage.py  worker_status

# View harvest progress
poetry run src/ubdc_airbnb/manage.py  harvest_progress --aoi_id 1
```

## GIS Integration

All collected data is stored in a PostGIS-enabled database, allowing for:
- Spatial analysis and visualization in GIS applications like QGIS
- Custom PostgreSQL user-defined functions for specialized geospatial queries
- Integration with other spatial data sources

# Development Guide

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
