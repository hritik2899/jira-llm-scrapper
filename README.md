# Apache Jira Scraper

A fault-tolerant, asynchronous data scraping pipeline that extracts public issue data from Apache's Jira instance and transforms it into a structured JSONL format suitable for training Large Language Models (LLMs).

## 📋 Table of Contents

- [Features](#features)
- [Architecture Overview](#architecture-overview)
- [Setup Instructions](#setup-instructions)
- [API Endpoints](#api-endpoints)
- [Edge Cases Handled](#edge-cases-handled)
- [Optimization Decisions](#optimization-decisions)
- [Data Format](#data-format)
- [Future Improvements](#future-improvements)

## ✨ Features

- **Asynchronous scraping** using `aiohttp` for efficient I/O operations
- **Fault-tolerant** with automatic retry mechanisms and exponential backoff
- **Resumable** scraping with checkpoint persistence
- **Rate limit handling** with automatic backoff on HTTP 429 responses
- **Real-time progress tracking** via API endpoints
- **Comprehensive statistics** generation for scraped datasets
- **RESTful API** built with FastAPI for easy integration

## 🏗️ Architecture Overview

### Design Philosophy

The scraper is built on three core principles:

1. **Resilience**: Network failures, rate limits, and malformed data are expected and handled gracefully
2. **Efficiency**: Asynchronous operations and smart checkpointing minimize redundant work
3. **Observability**: Rich status endpoints provide real-time insights into scraping progress

### Component Breakdown

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Layer                         │
│  (REST endpoints for control and monitoring)             │
└─────────────────┬───────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────┐
│              Scraping Engine                             │
│  • Async HTTP requests with aiohttp                      │
│  • Retry logic with exponential backoff                  │
│  • Rate limit detection and handling                     │
└─────────────────┬───────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────┐
│           Checkpoint System                              │
│  • JSON-based state persistence                          │
│  • Per-project progress tracking                         │
│  • Automatic recovery on restart                         │
└─────────────────┬───────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────┐
│              Data Pipeline                               │
│  • Field extraction and cleaning                         │
│  • JSONL serialization                                   │
│  • Derived task generation for LLM training              │
└──────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Fetch Issues**: Query Jira API with pagination (`startAt`, `maxResults`)
2. **Fetch Comments**: For each issue, retrieve associated comments
3. **Transform**: Extract relevant fields and structure data
4. **Persist**: Write to JSONL file with checkpoint update
5. **Resume**: On failure/restart, continue from last checkpoint

## 🚀 Setup Instructions

### Prerequisites

- Python 3.8+
- `pip` package manager

### Installation

1. **Clone the repository**:
```bash
git clone <your-repo-url>
cd apache-jira-scraper
```

2. **Create a virtual environment** (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

### Requirements.txt

Create a `requirements.txt` file with:
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
aiohttp==3.9.1
```

### Configuration

Edit the following constants in the code to customize scraping:

```python
PROJECTS = ["SPARK", "HADOOP", "KAFKA"]  # Projects to scrape
MAX_RESULTS = 10                          # Issues per API call
OUTPUT_FILE = "output.jsonl"              # Output filename
CHECKPOINT_FILE = "checkpoint.json"       # Checkpoint filename
```

### Running the Application

Start the FastAPI server:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

Interactive API documentation: `http://localhost:8000/docs`

## 📡 API Endpoints

### Core Endpoints

#### `GET /`
**Description**: Home endpoint with basic information  
**Response**:
```json
{
  "message": "Apache Jira Scraper API",
  "projects": ["SPARK", "HADOOP", "KAFKA"]
}
```

#### `POST /scrape`
**Description**: Start scraping process in background  
**Response**:
```json
{
  "status": "started",
  "message": "Scraping started in background",
  "projects": ["SPARK", "HADOOP", "KAFKA"],
  "timestamp": "2025-10-26T12:00:00"
}
```

#### `GET /transform`
**Description**: Transform scraped data to final JSONL format  
**Response**:
```json
{
  "message": "Transformed dataset saved to transformed_dataset.jsonl",
  "timestamp": "2025-10-26T12:30:00"
}
```

### Monitoring Endpoints

#### `GET /health`
**Description**: Health check endpoint  
**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-10-26T12:00:00",
  "service": "Apache Jira Scraper",
  "version": "1.0.0"
}
```

#### `GET /status`
**Description**: Get current scraping progress and checkpoint state  
**Response**:
```json
{
  "is_running": true,
  "start_time": "2025-10-26T11:00:00",
  "current_project": "SPARK",
  "projects_completed": ["HADOOP"],
  "progress": {
    "SPARK": {"scraped": 150, "completed": false},
    "HADOOP": {"scraped": 500, "completed": true},
    "KAFKA": {"scraped": 0, "completed": false}
  },
  "checkpoint_state": {
    "SPARK": 150,
    "HADOOP": 500,
    "KAFKA": 0
  },
  "output_file_exists": true,
  "output_file_size_mb": 12.5
}
```

#### `GET /stats`
**Description**: Get comprehensive dataset statistics  
**Response**:
```json
{
  "statistics": {
    "total_issues": 650,
    "by_project": {
      "SPARK": 150,
      "HADOOP": 500
    },
    "by_status": {
      "Resolved": 400,
      "Open": 150,
      "Closed": 100
    },
    "by_priority": {
      "Major": 300,
      "Minor": 200,
      "Critical": 150
    },
    "date_range": {
      "earliest": "2010-01-15T10:30:00.000+0000",
      "latest": "2025-10-25T14:20:00.000+0000"
    },
    "total_comments": 3250,
    "issues_with_comments": 480
  },
  "generated_at": "2025-10-26T12:00:00"
}
```

### Management Endpoints

#### `DELETE /reset`
**Description**: Clear all checkpoints and scraped data to start fresh  
**Response**:
```json
{
  "status": "reset_complete",
  "message": "All checkpoints and data cleared",
  "files_deleted": [
    "checkpoint.json",
    "status.json",
    "output.jsonl"
  ],
  "timestamp": "2025-10-26T12:00:00"
}
```

## 🛡️ Edge Cases Handled

### Network & API Issues

1. **Rate Limiting (HTTP 429)**
   - Detection: Checks response status code
   - Handling: 10-second wait before retry
   - Implementation: `fetch_with_retry()` function

2. **Server Errors (5xx)**
   - Detection: Status codes 500-599
   - Handling: Exponential backoff (2^attempt seconds)
   - Max retries: 5 attempts

3. **Connection Timeouts**
   - Timeout: 30 seconds per request
   - Retry: Exponential backoff up to 5 times
   - Fallback: Skip to next issue after max retries

4. **404 Not Found**
   - Handling: Log and return None
   - Behavior: Continue with remaining issues

### Data Inconsistencies

5. **Empty/Malformed JSON Responses**
   - Validation: Check for `issues` key in response
   - Handling: Log and skip to next batch
   - Recovery: Continue scraping remaining projects

6. **Missing Fields**
   - Strategy: Defensive `.get()` calls with defaults
   - Example: `fields.get("reporter", {}).get("displayName") if fields.get("reporter") else None`
   - Fallback: Empty string or None for missing data

7. **Empty Comments**
   - Filter: Only include comments with non-empty body
   - Implementation: `[c.get("body", "").strip() for c in data["comments"] if c.get("body")]`

8. **Missing Descriptions**
   - Fallback: Return empty string
   - QnA task: "No description available" as answer

### System Issues

9. **Interrupted Scraping**
   - Checkpoint: Saved after each batch
   - Recovery: Resumes from last successful state
   - Implementation: `load_checkpoint()` on startup

10. **File System Errors**
    - Handling: Append mode for output file
    - UTF-8 encoding: Ensures international character support
    - `ensure_ascii=False`: Preserves Unicode characters

11. **Concurrent Scraping Prevention**
    - Status check: Returns HTTP 409 if already running
    - Implementation: Global `scraping_status` state

## ⚡ Optimization Decisions

### Asynchronous Architecture

**Decision**: Use `aiohttp` and `asyncio` instead of synchronous requests

**Reasoning**:
- Jira API calls have high I/O wait time
- Async allows fetching comments concurrently while processing issues
- Can handle thousands of issues without blocking

**Trade-off**: Added complexity vs. 10-100x performance improvement

### Checkpoint Granularity

**Decision**: Save checkpoint after each batch (not per issue)

**Reasoning**:
- Balances data safety with file I/O overhead
- Per-issue checkpointing would cause excessive disk writes
- Per-project checkpointing risks losing too much progress

**Trade-off**: Small amount of duplicate work on restart vs. performance

### Batch Size

**Decision**: `MAX_RESULTS = 10` issues per API call

**Reasoning**:
- Smaller batches = more frequent checkpoints
- Reduces memory footprint
- Faster feedback loop for progress tracking
- Easier to respect rate limits

**Trade-off**: More API calls vs. better fault tolerance

### Comment Fetching Strategy

**Decision**: Fetch comments sequentially (not batched)

**Reasoning**:
- Jira API v2 doesn't support batch comment queries
- Sequential fetching is simpler and more reliable
- Async still allows efficient I/O

**Future Improvement**: Implement concurrent comment fetching with semaphore

### Error Handling Philosophy

**Decision**: "Continue on error" rather than "fail fast"

**Reasoning**:
- Partial data is better than no data
- Individual issue failures shouldn't halt entire scrape
- Issues are logged for manual review

**Trade-off**: Potential incomplete dataset vs. scraping resilience

### Storage Format

**Decision**: JSONL (JSON Lines) instead of single JSON array

**Reasoning**:
- Streaming writes without loading entire dataset
- Easy to append new data
- Line-based processing for large datasets
- Standard format for LLM training pipelines

**Trade-off**: Slightly less human-readable vs. much better performance

## 📄 Data Format

Each line in the output JSONL file contains:

```json
{
  "metadata": {
    "id": "12345",
    "key": "SPARK-1000",
    "title": "Issue summary",
    "project": "SPARK",
    "status": "Resolved",
    "priority": "Major",
    "reporter": "John Doe",
    "assignee": "Jane Smith",
    "labels": ["performance", "core"],
    "created": "2025-01-15T10:30:00.000+0000",
    "updated": "2025-01-20T14:00:00.000+0000"
  },
  "content": {
    "description": "Detailed issue description...",
    "comments": [
      "First comment text...",
      "Second comment text..."
    ]
  },
  "derived_tasks": {
    "summarization": "Summarize the issue and its discussion.",
    "classification": "Classify the issue as bug, improvement, or feature.",
    "qna": {
      "question": "What is the main problem discussed in issue SPARK-1000?",
      "answer": "Detailed issue description..."
    }
  }
}
```

### LLM Training Tasks

The `derived_tasks` field provides structured prompts for:

1. **Summarization**: Practice condensing technical discussions
2. **Classification**: Learn to categorize software issues
3. **QnA**: Extract information from technical documentation

## 🔮 Future Improvements

### Performance Enhancements

1. **Concurrent Project Scraping**
   ```python
   await asyncio.gather(*[scrape_project(p) for p in PROJECTS])
   ```
   - Scrape multiple projects simultaneously
   - Reduce total scraping time by 3x

2. **Connection Pooling**
   - Reuse TCP connections across requests
   - Reduce handshake overhead
   - Implement with `TCPConnector(limit=100)`

3. **Batch Comment Fetching**
   - Use semaphores to limit concurrent comment requests
   - Fetch 10-20 comments in parallel per issue

### Reliability Improvements

4. **File Locking**
   - Prevent concurrent writes to output file
   - Use `fcntl.flock()` or similar

5. **Data Validation**
   - Add schema validation with Pydantic
   - Detect and skip malformed issues
   - Generate data quality reports

6. **Duplicate Detection**
   - Track issue IDs to prevent duplicates
   - Useful for incremental updates

### Monitoring & Observability

7. **Structured Logging**
   - Replace `print()` with `logging` module
   - Add log levels (DEBUG, INFO, WARNING, ERROR)
   - Log rotation for long-running scrapers

8. **Metrics Collection**
   - Request latency tracking
   - Success/failure rates
   - Issues per second throughput

9. **Progress ETA**
   - Calculate estimated time remaining
   - Based on current scraping rate

### Feature Additions

10. **Incremental Updates**
    - Scrape only new issues since last run
    - Use `updated > lastScrapedDate` in JQL query

11. **Custom JQL Queries**
    - Allow users to specify custom filters
    - Example: Only critical bugs from last year

12. **Multi-format Export**
    - CSV export for spreadsheet analysis
    - Parquet for data warehousing
    - HuggingFace dataset format

13. **Configuration File**
    - YAML/JSON config for projects, rate limits, etc.
    - Environment variable support

### Advanced Optimizations

14. **Adaptive Rate Limiting**
    - Track rate limit headers from Jira
    - Dynamically adjust request rate
    - Maximize throughput while staying under limits

15. **Smart Retry Logic**
    - Different strategies for different error types
    - Circuit breaker pattern for persistent failures

16. **Distributed Scraping**
    - Multi-machine scraping with task queue (Celery/RabbitMQ)
    - Coordinate via Redis for checkpoints

## 📝 Usage Examples

### Basic Workflow

```bash
# 1. Start scraping
curl -X POST http://localhost:8000/scrape

# 2. Monitor progress
curl http://localhost:8000/status

# 3. Check statistics
curl http://localhost:8000/stats

# 4. Transform data
curl http://localhost:8000/transform

# 5. Reset and start over
curl -X DELETE http://localhost:8000/reset
```

### Resume After Interruption

```bash
# If scraping is interrupted (Ctrl+C, crash, etc.)
# Simply restart the server and call /scrape again
uvicorn main:app --reload
curl -X POST http://localhost:8000/scrape

# The scraper will automatically resume from the last checkpoint
```
