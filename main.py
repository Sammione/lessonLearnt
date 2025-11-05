from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import requests
import re
from config import BASE_URL, RECORDS_ENDPOINT, get_auth_headers

app = FastAPI(
    title="LUAN – Infracredit AI Lesson Learnt API",
    description="FastAPI backend for fetching and searching Lesson Learnt records.",
    version="1.0.1"
)

# ---------------------- CORS Configuration ----------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace * with your frontend domain if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------- Security ----------------------
security = HTTPBearer()


# ---------------------- Utility Functions ----------------------
def preprocess_query(query: str):
    """Extract relevant keywords from user query."""
    query = query.lower()
    stopwords = [
        "show", "me", "all", "the", "lessons", "learnt", "about", "in", "for",
        "mitigant", "mitigants", "risk", "issues", "record", "records", "lesson",
        "please", "can", "you", "display", "client", "sector", "counter-party",
        "counter", "party"
    ]
    return [w for w in re.findall(r'\w+', query) if w not in stopwords and len(w) > 2]


def clean_html(raw_text):
    """Remove HTML tags from text."""
    if not isinstance(raw_text, str):
        return raw_text
    return re.sub(r"<.*?>", "", raw_text).strip()


def fetch_all_records(token: str):
    """Fetch all transaction records across pages using user token."""
    all_results = []
    page = 1
    total_pages = 1

    print("\nFetching records across pages...")

    while page <= total_pages:
        url = f"{BASE_URL.rstrip('/')}{RECORDS_ENDPOINT}?page={page}"
        headers = get_auth_headers(token)

        try:
            response = requests.get(url, headers=headers, timeout=20)
            print(f"Fetching page {page} → Status {response.status_code}")

            if response.status_code == 401:
                raise HTTPException(status_code=401, detail="Invalid or expired token.")
            response.raise_for_status()

            data = response.json()
            print(f"Raw data keys: {list(data.keys())}")

            # --- Adjust this section to your API structure ---
            if isinstance(data, dict):
                if "data" in data:
                    inner = data["data"]
                    if isinstance(inner, dict):
                        results = inner.get("result") or inner.get("results") or inner.get("items") or []
                        total_pages = inner.get("totalPages") or inner.get("total_pages") or 1
                    elif isinstance(inner, list):
                        results = inner
                        total_pages = 1
                    else:
                        results = []
                else:
                    results = data.get("results", []) or []
                    total_pages = data.get("totalPages", 1)
            else:
                results = []

            if not results:
                print(f"No results on page {page}. Stopping.")
                break

            # Clean HTML fields
            for r in results:
                for field in ["title", "details", "lessonLearnt", "typeDescription"]:
                    if field in r and isinstance(r[field], str):
                        r[field] = clean_html(r[field])

            all_results.extend(results)
            page += 1

        except Exception as e:
            print(f"Error fetching page {page}: {e}")
            break

    print(f"Total records fetched: {len(all_results)}")
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


# ---------------------- Search Endpoint ----------------------
class SearchRequest(BaseModel):
    query: str


@app.post("/search")
def search_records_body(
    request: SearchRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Search for lessons or issues by keyword (using JSON body input)."""
    token = credentials.credentials
    query = request.query
    keywords = preprocess_query(query)

    if not keywords:
        raise HTTPException(status_code=400, detail="No valid keywords found in your query.")

    records = fetch_all_records(token)
    matches = []

    for r in records:
        combined_text = " ".join([
            str(r.get("title", "")),
            str(r.get("details", "")),
            str(r.get("lessonLearnt", "")),
            str(r.get("typeDescription", "")),
            str(r.get("consultantTransaction", {}).get("transactionName", "")),
            str(r.get("consultantTransaction", {}).get("portfolioName", "")),
            str(r.get("consultantTransaction", {}).get("sector", ""))
        ]).lower()

        if any(k in combined_text for k in keywords):
            matches.append(r)

    return {
        "query": query,
        "keywords": keywords,
        "total_matches": len(matches),
        "results": matches
    }


# ---------------------- Optional GET Version (for frontend) ----------------------
@app.get("/search")
def search_records_query(
    q: str = Query(..., alias="query"),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Search via URL query param, e.g., /search?query=energy"""
    request = SearchRequest(query=q)
    return search_records_body(request, credentials)
