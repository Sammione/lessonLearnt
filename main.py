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
    version="1.0.3"
)

# ---------------------- CORS Configuration ----------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace * with frontend domain if needed
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
    """Fetch all transaction records from API."""
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
            # Your API likely returns a list directly or a dict with `data` or `items`
            if isinstance(data, list):
                results = data
                total_pages = 1
            elif isinstance(data, dict):
                results = data.get("data") or data.get("items") or data.get("results") or []
                total_pages = data.get("totalPages") or data.get("total_pages") or 1
            else:
                results = []

            if not results:
                break

            for r in results:
                for field in ["title", "details", "lessonLearnt", "typeDescription"]:
                    if field in r and isinstance(r[field], str):
                        r[field] = clean_html(r[field])

            all_results.extend(results)
            page += 1

        except Exception as e:
            print(f"Error fetching page {page}: {e}")
            break

    print(f"✅ Total records fetched: {len(all_results)}")
    return all_results


# ---------------------- Bot Welcome Message ----------------------
def lesson_bot():
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
    return {"message": "Welcome to LUAN — Infracredit’s AI Lesson Learnt API"}


@app.get("/bot-welcome")
def bot_welcome():
    return {"welcome": lesson_bot()}


@app.get("/records")
def get_records(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Fetch all records using user's Bearer token."""
    token = credentials.credentials
    records = fetch_all_records(token)

    if not records:
        raise HTTPException(status_code=404, detail="No records found.")
    return {"total": len(records), "records": records}


# ---------------------- Search Endpoint ----------------------
@app.get("/search")
def search_records(
    query: str = Query(..., description="Search by project, portfolio, or sector name"),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Search transaction records by keyword (case-insensitive)."""
    token = credentials.credentials
    keywords = preprocess_query(query)

    if not keywords:
        raise HTTPException(status_code=400, detail="No valid keywords found in your query.")

    records = fetch_all_records(token)
    matches = []

    for r in records:
        transaction = r.get("consultantTransaction", {})
        combined_text = " ".join([
            str(transaction.get("portfolioName", "")),
            str(transaction.get("transactionName", "")),
            str(transaction.get("sector", "")),
            str(r.get("title", "")),
            str(r.get("details", "")),
        ]).lower()

        if any(k in combined_text for k in keywords):
            matches.append({
                "portfolioName": transaction.get("portfolioName"),
                "transactionName": transaction.get("transactionName"),
                "sector": transaction.get("sector"),
                "title": r.get("title"),
                "lessonLearnt": r.get("lessonLearnt")
            })

    if not matches:
        return {"message": f"No records found for '{query}'"}

    return {
        "query": query,
        "keywords": keywords,
        "total_matches": len(matches),
        "results": matches
    }
