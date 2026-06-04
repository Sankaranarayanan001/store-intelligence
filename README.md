## Instructions to Run

### Step 1: Clone the Repository

```bash
git clone https://github.com/<your-username>/store-intelligence.git
cd store-intelligence
```

### Step 2: Start the Application

Build and start all services using Docker:

```bash
docker compose up --build
```

During startup the application will:

- Initialize the SQLite database
- Load POS transaction data
- Ingest retail event data
- Start the FastAPI server
- Serve the analytics dashboard

### Step 3: Access the Dashboard

Open the following URL in your browser:

```text
http://localhost:8000/dashboard
```

### Step 4: Verify the APIs

Health Check:

```text
http://localhost:8000/health
```

Store Metrics:

```text
http://localhost:8000/stores/STORE_BLR_001/metrics
http://localhost:8000/stores/STORE_BLR_002/metrics
```

Conversion Funnel:

```text
http://localhost:8000/stores/STORE_BLR_001/funnel
http://localhost:8000/stores/STORE_BLR_002/funnel
```

Anomaly Detection:

```text
http://localhost:8000/stores/STORE_BLR_001/anomalies
http://localhost:8000/stores/STORE_BLR_002/anomalies
```

### Step 5: Stop the Application

To stop all running containers:

```bash
docker compose down
```

### Expected Outcome

After startup, the dashboard should display:

- Unique visitor counts
- Conversion rates
- Queue depth metrics
- Conversion funnel analytics
- Zone activity insights
- Anomaly detection alerts
- Store health monitoring

# Apex Retail Store Intelligence Platform

AI-powered retail analytics platform that converts CCTV footage and retail event streams into actionable business intelligence. The system processes customer movement across multiple store cameras, tracks visitor journeys, analyzes conversion funnels, monitors queue activity, and provides operational insights through a web dashboard.

---

## Overview

The Apex Retail Store Intelligence Platform helps retailers understand customer behavior inside physical stores. By combining computer vision generated events with POS transaction data, the platform provides visibility into visitor traffic, zone engagement, checkout activity, conversion performance, and operational anomalies.

Key Features:

- Visitor tracking and session management
- Conversion funnel analytics
- Zone activity and dwell-time analysis
- Queue depth monitoring
- Store health monitoring
- Operational anomaly detection
- POS transaction integration
- Multi-store analytics dashboard
- Docker-based deployment

---

## Technology Stack

| Component        | Technology              |
| ---------------- | ----------------------- |
| Backend API      | FastAPI                 |
| Database         | SQLite + aiosqlite      |
| Detection Model  | YOLOv8n                 |
| Tracking         | ByteTrack               |
| Validation       | Pydantic                |
| Containerization | Docker & Docker Compose |
| Frontend         | HTML, CSS, JavaScript   |
| Testing          | Pytest                  |

---

## System Architecture

The platform consists of four major layers:

### Detection Layer

Camera footage is processed using YOLOv8n and ByteTrack to detect and track individuals. The pipeline generates structured events such as:

- ENTRY
- EXIT
- REENTRY
- ZONE_ENTER
- ZONE_DWELL
- BILLING_QUEUE_JOIN

### Event Processing Layer

Generated events are normalized into a common schema and stored in the analytics database. Visitor sessions are maintained separately to support funnel calculations and customer journey analysis.

### Analytics Layer

The analytics engine computes:

- Unique visitors
- Conversion rate
- Funnel progression
- Queue depth
- Zone dwell time
- Store health metrics
- Operational anomalies

### Visualization Layer

A web dashboard presents analytics and operational insights for retail managers.

---

## Supported Camera Types

| Camera Type                | Purpose                                          |
| -------------------------- | ------------------------------------------------ |
| Entry/Exit Cameras         | Detect customer entry, exit, and re-entry events |
| Zone Monitoring Cameras    | Track customer movement and dwell time           |
| Billing Area Cameras       | Monitor checkout activity and queue depth        |
| Store Surveillance Cameras | Generate behavioral events for analytics         |

The platform supports multiple cameras deployed across multiple retail stores.

---

## Running the Project

### Prerequisites

- Docker Desktop
- Git

### Clone Repository

```bash
git clone <repository-url>
cd store-intelligence
```

### Start the Application

```bash
docker compose up --build
```

During startup the system automatically:

1. Initializes the SQLite database
2. Loads POS transaction data
3. Loads and ingests retail event data
4. Starts the FastAPI server
5. Serves the analytics dashboard

---

## Dashboard

After startup, open:

```text
http://localhost:8000/dashboard
```

The dashboard provides:

- Live visitor metrics
- Conversion funnel visualization
- Zone activity analysis
- Queue monitoring
- Anomaly detection
- Store health monitoring

---

## API Endpoints

### Health Status

```http
GET /health
```

### Store Metrics

```http
GET /stores/{store_id}/metrics
```

### Conversion Funnel

```http
GET /stores/{store_id}/funnel
```

### Anomaly Detection

```http
GET /stores/{store_id}/anomalies
```

---

## Example Stores

```text
STORE_BLR_001
STORE_BLR_002
```

---

## Testing

Run the test suite:

```bash
pytest tests/ -v
```

The tests validate:

- Metrics calculations
- Funnel analytics
- Anomaly detection
- Event ingestion
- API functionality

---

## AI-Assisted Development

Claude AI and GitHub Copilot were used during development for architecture discussions, design reviews, trade-off analysis, and implementation guidance.

AI assistance influenced:

- Event schema design
- Analytics architecture
- Staff detection strategy
- Database design decisions
- API structure
- Documentation improvements

Final implementation decisions, integration, testing, debugging, and validation were performed manually.

---

## Future Enhancements

Potential improvements include:

- Real-time camera streaming
- PostgreSQL deployment
- Advanced customer re-identification
- Machine learning based anomaly detection
- Cloud-native deployment
- Historical trend analysis
- Role-based access control

---

## License

This project was developed as a retail analytics and store intelligence solution for educational, research, and assessment purposes.
