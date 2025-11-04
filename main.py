from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import requests
import re
from config import BASE_URL, RECORDS_ENDPOINT, get_auth_headers

app = FastAPI(
    title="LUAN – Infracredit AI Lesson Learnt API",
    description="FastAPI backend for fetching and searching Lesson Learnt records.",
    version="1.0.0"
)

# Allow frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict this to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()


# ---------------------- Utility Functions ----------------------
def preprocess_query(query: str):
    """Extract relevant keywords from user query."""
    query = query.lower()
    stopwords = [
        "show", "me", "all", "the", "lessons", "learnt", "about", "in", "for", "mitigant",
        "mitigants", "risk", "issues", "record", "records", "lesson", "please", "can",
        "you", "display", "client", "sector", "counter-party", "counter", "party"
    ]
    return [w for w in re.findall(r'\w+', query) if w not in stopwords]


def clean_html(raw_text):
    """Remove HTML tags from text."""
    if not isinstance(raw_text, str):
        return raw_text
    return re.sub(r"<.*?>", "", raw_text).strip()


def fetch_all_records(token: str):
    """Fetch all records across pages using user token."""
    all_results = []
    page = 1
    total_pages = 1

    print("\n Fetching records across pages...")

    while page <= total_pages:
        url = f"{BASE_URL}{RECORDS_ENDPOINT}?page={page}"
        headers = get_auth_headers(token)

        try:
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            data = response.json()

            # Flexible parsing
            if isinstance(data, dict):
                if "data" in data and isinstance(data["data"], dict):
                    results = data["data"].get("result") or data["data"].get("results") or []
                    total_pages = data["data"].get("totalPages") or data["data"].get("total_pages") or total_pages
                elif "results" in data:
                    results = data.get("results", [])
                    total_pages = data.get("totalPages") or data.get("total_pages") or total_pages
                elif isinstance(data.get("data"), list):
                    results = data["data"]
                else:
                    results = data if isinstance(data, list) else []
            else:
                results = []

            if not results:
                break

            # Clean HTML tags
            for r in results:
                for field in ["title", "details", "lessonLearnt", "typeDescription"]:
                    if field in r:
                        r[field] = clean_html(r[field])

            all_results.extend(results)
            page += 1

        except Exception as e:
            print(f"Error fetching page {page}: {e}")
            break

    return all_results


# ---------------------- Bot Welcome Function ----------------------
def lesson_bot():
    """Interactive bot welcome message."""
    return {
        "title": "Hi, I’m LUAN — Infracredit’s AI Lesson Learnt Bot.",
        "intro": "Ask me things like:",
        "examples": [
            "→ Tell me all the Risk issues and mitigants for Counter-Party Pirano Energy",
            "→ List all the Risk issues and mitigants for sector Clean Energy",
            "→ Show me all the Risk issues and mitigants for Market Risk"
        ]
    }


# ---------------------- API Endpoints ----------------------
@app.get("/")
def root():
    """Root endpoint for API health/status."""
    return {"message": "Welcome to LUAN — Infracredit’s AI Lesson Learnt API"}


@app.get("/bot-welcome")
def bot_welcome():
    """Endpoint for bot frontend to display welcome message when opened."""
    return {"welcome": lesson_bot()}


@app.get("/records")
def get_records(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Fetch all records using the user's token."""
    token = credentials.credentials
    records = fetch_all_records(token)

    if not records:
        raise HTTPException(status_code=404, detail="No records found.")
    return {"total": len(records), "records": records}


@app.get("/search")
def search_records(
    query: str = Query(..., description="Enter search keywords (e.g., 'Pirano Energy risk issues')"),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Search for lessons or issues by keyword."""
    token = credentials.credentials
    keywords = preprocess_query(query)

    if not keywords:
        raise HTTPException(status_code=400, detail="No valid keywords found in your query.")

    records = fetch_all_records(token)
    matches = []

    for r in records:
        combined_text = " ".join([
            str(r.get("title", "") or ""),
            str(r.get("details", "") or ""),
            str(r.get("lessonLearnt", "") or ""),
            str(r.get("typeDescription", "") or ""),
            str(r.get("consultantTransaction", {}).get("transactionName", "") or ""),
            str(r.get("consultantTransaction", {}).get("portfolioName", "") or ""),
            str(r.get("consultantTransaction", {}).get("sector", "") or "")
        ]).lower()

        if any(k in combined_text for k in keywords):
            matches.append(r)

    return {
        "query": query,
        "keywords": keywords,
        "total_matches": len(matches),
        "results": matches
    }
