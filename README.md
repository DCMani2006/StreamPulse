# StreamPulse Backend

> **High-Throughput, Event-Driven Real-Time Media Ingestion & Distributed ML Analytics Pipeline Engineered for Sub-300ms End-to-End Latency.**

---

## 🌟 Overview & Architecture

StreamPulse is a distributed stream processing backend designed to ingest live video keyframes and audio chunks from edge devices, execute deep learning object detection (Ultralytics YOLOv8) and digital audio signal processing, evaluate dynamic security rules in real-time, and broadcast latency-stamped telemetry to client dashboards within **sub-300ms SLA**.

```
[ Edge Devices / test_stream.py ]
          │ (Duplex WebSocket / HTTP POST)
          ▼
┌─────────────────────────────────────────────────────────┐
│ FastAPI Ingestion Gateway (/ws/ingest/{stream_id})      │
│  - Captures arrival timestamp t_ingest                  │
│  - Non-blocking XADD to Redis Stream                    │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
               [ Redis 7.x Stream Queue ]
                 (stream:video:raw)
                           │
                           ▼ (XREADGROUP Consumer Group)
┌─────────────────────────────────────────────────────────┐
│ Distributed ML Inference Workers (worker.py)            │
│  - YOLOv8 Nano CPU-Optimized Object Detection           │
│  - Audio RMS & Zero-Crossing Rate (ZCR) VAD             │
│  - Dynamic Alert & Intrusion Rule Evaluation            │
│  - Granular 4-Stage Latency Computation                 │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼ (Redis Pub/Sub)
                [ channel:telemetry:{stream_id} ]
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│ Telemetry Broadcast Gateway (/ws/telemetry/{stream_id}) │
│  - Multiplexed WebSocket streaming to Dashboards        │
│  - REST Telemetry & SLA Metrics (/api/v1/metrics)       │
└─────────────────────────────────────────────────────────┘
```

---

## ⏱️ Latency Budget & 4-Stage Breakdown

StreamPulse measures high-resolution latency across every stage of processing:

| Stage | Formula | Target Budget |
| :--- | :--- | :--- |
| **Ingestion Network Latency** | $t_{\text{ingest}} - t_{\text{client}}$ | $< 35\text{ ms}$ |
| **Queue Dwell Time** | $t_{\text{worker\_start}} - t_{\text{ingest}}$ | $< 15\text{ ms}$ |
| **ML Inference Time (YOLOv8 + Audio)** | $t_{\text{worker\_done}} - t_{\text{worker\_start}}$ | $< 120\text{ ms}$ |
| **Pub/Sub & Broadcast Latency** | $t_{\text{broadcast}} - t_{\text{worker\_done}}$ | $< 10\text{ ms}$ |
| **Total End-to-End (E2E) Latency** | $t_{\text{broadcast}} - t_{\text{client}}$ | **$< 180 - 280\text{ ms}$ (SLA: $< 300\text{ ms}$)** |

---

## 📁 Directory Structure

```text
streampulse-backend/
├── app/
│   ├── __init__.py          # Package initialization
│   ├── main.py              # FastAPI app, WebSocket routers & REST endpoints
│   ├── config.py            # Pydantic Settings & environment configuration
│   ├── schemas.py           # Pydantic models for frames, alerts, telemetry, and metrics
│   ├── redis_client.py      # Async Redis connection pool, streams, pubsub & metrics
│   ├── worker.py            # Distributed ML worker (YOLOv8 inference & audio DSP)
│   └── pipeline_utils.py    # OpenCV base64 decoders, bounding box math & audio DSP
├── test_stream.py           # End-to-end webcam & synthetic stream tester with live HUD
├── requirements.txt         # Pinned production dependencies
├── Dockerfile               # Production multi-stage Docker build
├── docker-compose.yml       # 1-click startup for Redis, App, and Worker
└── README.md                # Documentation and operation guide
```

---

## 🚀 Quickstart (Docker Compose)

The fastest way to launch the entire stack is with Docker Compose:

```bash
# 1. Start Redis, FastAPI Gateway, and ML Worker
docker-compose up --build
```

To horizontally scale ML workers to handle higher load across CPU cores:
```bash
docker-compose up --scale worker=3
```

Check system status:
```bash
curl http://localhost:8000/health
```

---

## 💻 Local Development Setup (Localhost)

### 1. Prerequisites
- Python 3.11+
- Redis Server (local or via `docker run -d -p 6379:6379 redis:7-alpine`)

### 2. Install Dependencies
```bash
python -m venv venv
# On Linux/macOS:
source venv/bin/activate
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 3. Start Application Gateway
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Start ML Worker in a Separate Terminal
```bash
python -m app.worker
```

---

## 🧪 Real-Time Testing Suite (`test_stream.py`)

`test_stream.py` provides an end-to-end testing client with an interactive OpenCV Heads-Up Display (HUD). It captures local webcam frames, streams them to `/ws/ingest/cam_01`, and subscribes to `/ws/telemetry/cam_01` to display real-time bounding boxes, alerts, and latency waterfall metrics.

### Run with Local Webcam:
```bash
python test_stream.py --stream-id cam_01 --fps 10
```

### Run with Synthetic Video Generator (Zero Hardware Dependencies):
```bash
python test_stream.py --stream-id cam_01 --fps 10 --synthetic
```

### Run in Headless Mode (CI/CD or Remote Servers):
```bash
python test_stream.py --stream-id cam_01 --fps 10 --synthetic --no-gui --duration 30
```

---

## 📡 API Reference & WebSocket Endpoints

### 1. Ingestion Layer

#### `WS /ws/ingest/{stream_id}`
Duplex low-latency WebSocket endpoint for edge devices.

**Incoming Frame Message (JSON):**
```json
{
  "stream_id": "cam_01",
  "sequence_id": 1042,
  "t_client": 1724912345.1234,
  "frame_base64": "/9j/4AAQSkZJRgABAQAAAQABAAD...",
  "audio_base64": "AAAA//8BAA...",
  "metadata": { "location": "Warehouse Entrance A" }
}
```

**Ingest Acknowledgment (JSON):**
```json
{
  "status": "queued",
  "sequence_id": 1042,
  "msg_id": "1724912345125-0",
  "t_ingest": 1724912345.145
}
```

#### `POST /api/v1/stream/ingest`
HTTP POST fallback endpoint for legacy devices with identical JSON payload format.

---

### 2. Telemetry & Broadcast Gateway

#### `WS /ws/telemetry/{stream_id}`
Real-time fan-out broadcast WebSocket subscribed to Redis Pub/Sub.

**Broadcast Telemetry Payload (JSON):**
```json
{
  "stream_id": "cam_01",
  "sequence_id": 1042,
  "timestamp": 1724912345.241,
  "worker_id": "worker-streampulse-node-1",
  "person_count": 2,
  "total_objects": 3,
  "detections": [
    {
      "class_id": 0,
      "label": "person",
      "confidence": 0.892,
      "box": [120.5, 85.0, 240.0, 390.0],
      "normalized_box": [0.188, 0.177, 0.375, 0.812]
    }
  ],
  "audio_analysis": {
    "energy_rms": 0.024,
    "energy_db": -32.4,
    "zero_crossing_rate": 0.12,
    "voice_activity_detected": true,
    "spike_detected": false
  },
  "alerts": [],
  "latency": {
    "t_client": 1724912345.1234,
    "t_ingest": 1724912345.1450,
    "t_worker_start": 1724912345.1520,
    "t_worker_done": 1724912345.2390,
    "t_broadcast": 1724912345.2410,
    "ingestion_latency_ms": 21.6,
    "queue_dwell_time_ms": 7.0,
    "inference_time_ms": 87.0,
    "e2e_latency_ms": 117.6,
    "sla_met": true
  },
  "frame_width": 640,
  "frame_height": 480
}
```

---

### 3. REST Metrics & System Health

#### `GET /health`
Verifies Redis connection latency, active worker heartbeats, queue depth, and memory stats:
```json
{
  "status": "healthy",
  "app_name": "StreamPulse",
  "environment": "production",
  "redis_connected": true,
  "redis_latency_ms": 0.85,
  "active_workers_count": 2,
  "queue_depth": 0,
  "system_memory_used_mb": 245.8,
  "system_cpu_percent": 14.2,
  "uptime_seconds": 1240.5,
  "timestamp": 1724912350.0
}
```

#### `GET /api/v1/metrics?stream_id=cam_01&window_sec=60`
Returns rolling 60-second averages and SLA compliance percentages:
```json
{
  "stream_id": "cam_01",
  "time_window_seconds": 60,
  "total_frames_processed": 600,
  "fps": 10.0,
  "avg_e2e_latency_ms": 134.2,
  "avg_ingestion_latency_ms": 24.1,
  "avg_queue_dwell_time_ms": 8.5,
  "avg_inference_time_ms": 98.4,
  "p95_e2e_latency_ms": 182.0,
  "current_queue_depth": 0,
  "total_alerts_triggered": 1,
  "sla_compliance_percent": 99.8
}
```

#### `POST /api/v1/alerts/config`
Updates dynamic alert rules and security perimeters:
```json
{
  "stream_id": "cam_01",
  "max_persons": 3,
  "restricted_zone": [0.2, 0.2, 0.8, 0.8],
  "audio_energy_threshold": 0.08,
  "enable_person_alert": true,
  "enable_zone_alert": true,
  "enable_audio_alert": true
}
```

#### `GET /api/v1/alerts/history?stream_id=cam_01&limit=50`
Retrieves recent security incident logs.

---

## 🔒 Production Readiness & Resilience

1. **Decoupled Backpressure Handling:** Redis Streams buffer incoming bursts without blocking network ingestion sockets.
2. **Auto-Recovery of Dead Workers:** Workers run `XAUTOCLAIM` periodically to rescue unacknowledged messages from failed instances.
3. **Model Warmup on Boot:** YOLOv8 executes a warm-up pass during worker boot to eliminate PyTorch initialization latency spikes on the first frame.
4. **Non-Blocking I/O:** Fully asynchronous Redis operations, event loops, and WebSocket connection managers.
