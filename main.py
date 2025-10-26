import aiohttp
import asyncio
import json
import os
from datetime import datetime
from collections import defaultdict
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="Apache Jira Scraper")

JIRA_API_URL = "https://issues.apache.org/jira/rest/api/2"
PROJECTS = ["SPARK", "HADOOP", "KAFKA"]
MAX_RESULTS = 10
OUTPUT_FILE = "output.jsonl"
CHECKPOINT_FILE = "checkpoint.json"
STATUS_FILE = "status.json"

# Global scraping status
scraping_status = {
    "is_running": False,
    "start_time": None,
    "current_project": None,
    "projects_completed": []
}


# ------------------ Utility Functions ------------------

def load_checkpoint():
    if not os.path.exists(OUTPUT_FILE):
        # if data file deleted, reset checkpoint too
        return {p: 0 for p in PROJECTS}
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            return json.load(f)
    return {p: 0 for p in PROJECTS}


def save_checkpoint(state):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(state, f)


def update_status(is_running=None, current_project=None, completed_project=None):
    """Update the global scraping status"""
    if is_running is not None:
        scraping_status["is_running"] = is_running
        if is_running:
            scraping_status["start_time"] = datetime.now().isoformat()
            scraping_status["projects_completed"] = []
        else:
            scraping_status["start_time"] = None
            scraping_status["current_project"] = None
    
    if current_project is not None:
        scraping_status["current_project"] = current_project
    
    if completed_project and completed_project not in scraping_status["projects_completed"]:
        scraping_status["projects_completed"].append(completed_project)
    
    # Save to file for persistence
    with open(STATUS_FILE, "w") as f:
        json.dump(scraping_status, f)


async def fetch_with_retry(session, url, retries=5):
    for attempt in range(retries):
        try:
            async with session.get(url, ssl=False, timeout=30) as resp:
                if resp.status == 429:
                    print("Rate limited — waiting 10 seconds...")
                    await asyncio.sleep(10)
                    continue
                if 500 <= resp.status < 600:
                    await asyncio.sleep(2 ** attempt)
                    continue
                if resp.status == 404:
                    print(f"404 Not Found: {url}")
                    return None
                return await resp.json()
        except Exception as e:
            print(f"Retry {attempt + 1} due to {e}")
            await asyncio.sleep(2 ** attempt)
    return None


# ------------------ Scraping Logic ------------------

async def fetch_comments(session, issue_key):
    """Fetch comments for a single issue"""
    url = f"{JIRA_API_URL}/issue/{issue_key}/comment"
    data = await fetch_with_retry(session, url)
    if not data or "comments" not in data:
        return []
    return [c.get("body", "").strip() for c in data["comments"] if c.get("body")]


async def scrape_project(project: str):
    checkpoint = load_checkpoint()
    start_at = checkpoint.get(project, 0)
    total = None
    
    update_status(current_project=project)

    async with aiohttp.ClientSession() as session:
        while True:
            url = f"{JIRA_API_URL}/search?jql=project={project}&startAt={start_at}&maxResults={MAX_RESULTS}"
            data = await fetch_with_retry(session, url)
            if not data or "issues" not in data:
                print(f"Skipping empty/malformed response for {project}")
                break

            issues = data["issues"]
            if not issues:
                break

            with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                for issue in issues:
                    issue_key = issue.get("key")
                    comments = await fetch_comments(session, issue_key)
                    cleaned = extract_fields(issue, comments)
                    f.write(json.dumps(cleaned, ensure_ascii=False) + "\n")
            
            start_at += len(issues)
            checkpoint[project] = start_at
            save_checkpoint(checkpoint)

            total = data.get("total", None)
            print(f"{project}: Fetched {start_at}/{total}")

            await asyncio.sleep(1)

            if total and start_at >= total:
                break
    
    update_status(completed_project=project)


def extract_fields(issue, comments):
    fields = issue.get("fields", {})
    return {
        "metadata": {
            "id": issue.get("id"),
            "key": issue.get("key"),
            "title": fields.get("summary"),
            "project": fields.get("project", {}).get("key"),
            "status": fields.get("status", {}).get("name"),
            "priority": fields.get("priority", {}).get("name"),
            "reporter": fields.get("reporter", {}).get("displayName") if fields.get("reporter") else None,
            "assignee": fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
            "labels": fields.get("labels", []),
            "created": fields.get("created"),
            "updated": fields.get("updated")
        },
        "content": {
            "description": fields.get("description") or "",
            "comments": comments
        },
        "derived_tasks": {
            "summarization": "Summarize the issue and its discussion.",
            "classification": "Classify the issue as bug, improvement, or feature.",
            "qna": {
                "question": f"What is the main problem discussed in issue {issue.get('key')}?",
                "answer": fields.get("description") or "No description available."
            }
        }
    }


# ------------------ Statistics Functions ------------------

def calculate_stats():
    """Calculate dataset statistics"""
    if not os.path.exists(OUTPUT_FILE):
        return None
    
    stats = {
        "total_issues": 0,
        "by_project": defaultdict(int),
        "by_status": defaultdict(int),
        "by_priority": defaultdict(int),
        "date_range": {
            "earliest": None,
            "latest": None
        },
        "total_comments": 0,
        "issues_with_comments": 0
    }
    
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                issue = json.loads(line)
                stats["total_issues"] += 1
                
                # Project stats
                project = issue.get("metadata", {}).get("project")
                if project:
                    stats["by_project"][project] += 1
                
                # Status stats
                status = issue.get("metadata", {}).get("status")
                if status:
                    stats["by_status"][status] += 1
                
                # Priority stats
                priority = issue.get("metadata", {}).get("priority")
                if priority:
                    stats["by_priority"][priority] += 1
                
                # Date range
                created = issue.get("metadata", {}).get("created")
                if created:
                    if stats["date_range"]["earliest"] is None or created < stats["date_range"]["earliest"]:
                        stats["date_range"]["earliest"] = created
                    if stats["date_range"]["latest"] is None or created > stats["date_range"]["latest"]:
                        stats["date_range"]["latest"] = created
                
                # Comment stats
                comments = issue.get("content", {}).get("comments", [])
                stats["total_comments"] += len(comments)
                if comments:
                    stats["issues_with_comments"] += 1
                    
            except json.JSONDecodeError:
                continue
    
    # Convert defaultdict to regular dict for JSON serialization
    stats["by_project"] = dict(stats["by_project"])
    stats["by_status"] = dict(stats["by_status"])
    stats["by_priority"] = dict(stats["by_priority"])
    
    return stats


# ------------------ FastAPI Routes ------------------

@app.get("/")
def home():
    return {"message": "Apache Jira Scraper API", "projects": PROJECTS}


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "Apache Jira Scraper",
        "version": "1.0.0"
    }


@app.get("/status")
def get_status():
    """Get current scraping status and progress"""
    checkpoint = load_checkpoint()
    
    # Calculate progress for each project
    progress = {}
    for project in PROJECTS:
        scraped = checkpoint.get(project, 0)
        progress[project] = {
            "scraped": scraped,
            "completed": project in scraping_status.get("projects_completed", [])
        }
    
    return {
        "is_running": scraping_status["is_running"],
        "start_time": scraping_status["start_time"],
        "current_project": scraping_status["current_project"],
        "projects_completed": scraping_status["projects_completed"],
        "progress": progress,
        "checkpoint_state": checkpoint,
        "output_file_exists": os.path.exists(OUTPUT_FILE),
        "output_file_size_mb": round(os.path.getsize(OUTPUT_FILE) / (1024 * 1024), 2) if os.path.exists(OUTPUT_FILE) else 0
    }


@app.get("/stats")
def get_stats():
    """Get dataset statistics"""
    stats = calculate_stats()
    
    if stats is None:
        raise HTTPException(
            status_code=404,
            detail="No data found. Please run /scrape first."
        )
    
    return {
        "statistics": stats,
        "generated_at": datetime.now().isoformat()
    }


@app.delete("/reset")
def reset_scraper():
    """Clear checkpoints and start fresh"""
    files_deleted = []
    
    # Delete checkpoint file
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
        files_deleted.append(CHECKPOINT_FILE)
    
    # Delete status file
    if os.path.exists(STATUS_FILE):
        os.remove(STATUS_FILE)
        files_deleted.append(STATUS_FILE)
    
    # Delete output file
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)
        files_deleted.append(OUTPUT_FILE)
    
    # Reset global status
    scraping_status["is_running"] = False
    scraping_status["start_time"] = None
    scraping_status["current_project"] = None
    scraping_status["projects_completed"] = []
    
    return {
        "status": "reset_complete",
        "message": "All checkpoints and data cleared",
        "files_deleted": files_deleted,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/scrape")
async def start_scraping(background_tasks: BackgroundTasks):
    """Start scraping all configured projects in background"""
    if scraping_status["is_running"]:
        raise HTTPException(
            status_code=409,
            detail="Scraping is already in progress"
        )
    
    update_status(is_running=True)
    background_tasks.add_task(run_scraper)
    
    return JSONResponse({
        "status": "started",
        "message": "Scraping started in background",
        "projects": PROJECTS,
        "timestamp": datetime.now().isoformat()
    })


async def run_scraper():
    try:
        for project in PROJECTS:
            await scrape_project(project)
        print("✅ Scraping completed!")
    finally:
        update_status(is_running=False)


@app.get("/transform")
def transform_to_jsonl():
    """Flattened version for LLM training"""
    if not os.path.exists(OUTPUT_FILE):
        raise HTTPException(
            status_code=404,
            detail="No data found. Please run /scrape first."
        )

    jsonl_path = "transformed_dataset.jsonl"
    with open(OUTPUT_FILE, "r", encoding="utf-8") as infile, open(jsonl_path, "w", encoding="utf-8") as outfile:
        for line in infile:
            issue = json.loads(line)
            outfile.write(json.dumps(issue, ensure_ascii=False) + "\n")

    return {
        "message": f"Transformed dataset saved to {jsonl_path}",
        "timestamp": datetime.now().isoformat()
    }