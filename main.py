from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import requests
import re
from config import BASE_URL, RECORDS_ENDPOINT

app = FastAPI(
    title="LUAN – Infracredit AI Lesson Learnt API",
    description="FastAPI backend for fetching and searching Lesson Learnt records.",
    version="1.0.9"
)

# ---------------------- CORS Configuration ----------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------- Utility Functions ----------------------
def preprocess_query(query: str):
    query = query.lower()
    stopwords = [
        "show", "me", "all", "the", "lessons", "learnt", "about", "in", "for",
        "mitigant", "mitigants", "risk", "issues", "record", "records", "lesson",
        "please", "can", "you", "display", "client", "sector", "counter-party",
        "counter", "party", "tell", "give", "list"
    ]
    return [w for w in re.findall(r'\w+', query) if w not in stopwords and len(w) > 2]

def clean_html(raw_text):
    if not isinstance(raw_text, str):
        return raw_text
    return re.sub(r"<.*?>", "", raw_text).strip()

def extract_records(data):
    """
    Recursively search for a list of dicts (records) in API response.
    """
    if isinstance(data, list):
        if all(isinstance(i, dict) for i in data):
            return data
        return []
    elif isinstance(data, dict):
        for v in data.values():
            result = extract_records(v)
            if result:
                return result
    return []

def fetch_all_records(token: str):
    """Fetch all records using token. Tries both 'token' and 'Authorization: Bearer <token>'."""
    all_results = []
    page = 1
    total_pages = 1

    while page <= total_pages:
        url = f"{BASE_URL.rstrip('/')}{RECORDS_ENDPOINT}?page={page}"

        # Try both header types
        headers_options = [
            {"token": token, "Content-Type": "application/json"},
            {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        ]

        response = None
        for headers in headers_options:
            try:
                response = requests.get(url, headers=headers, timeout=20)
                if response.status_code == 200:
                    break  # success
            except Exception as e:
                print(f"Request failed with headers {headers}: {e}")
                continue

        if response is None or response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code if response else 500,
                detail="Failed to fetch records. Token may be invalid or expired."
            )

        data = response.json()
        print(f"Raw API response (page {page}): {data}")

        results = extract_records(data)
        if not results:
            print(f"No records found on page {page}")
            break

        # Try to get total pages if available
        if isinstance(data, dict):
            total_pages = data.get("totalPages") or data.get("total_pages") or 1

        # Clean HTML fields
        for r in results:
            for field in ["title", "details", "lessonLearnt", "typeDescription"]:
                if field in r and isinstance(r[field], str):
                    r[field] = clean_html(r[field])

        all_results.extend(results)
        page += 1

    print(f"Total records fetched: {len(all_results)}")
    if all_results:
        print("Sample record keys:", all_results[0].keys())

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
def bot_welcome(token: str = Header(..., description="User login token")):
    """Return welcome message with examples."""
    return {"welcome": lesson_bot()}

@app.get("/records")
def get_records(token: str = Header(..., description="Access token for authentication")):
    """Fetch all records using user's token in header."""
    records = fetch_all_records(token)
    if not records:
        raise HTTPException(status_code=404, detail="No records found.")
    return {"total": len(records), "records": records}

@app.get("/search")
def search_records(
    query: str = Query(..., description="Search by portfolio name, sector, project type, title, or description"),
    token: str = Header(..., description="Access token for authentication")
):
    """Search transaction records by keywords across all fields."""
    keywords = preprocess_query(query)
    if not keywords:
        raise HTTPException(status_code=400, detail="No valid keywords found in your query.")

    records = fetch_all_records(token)
    matches = []

    # Recursive function to gather all text from nested dicts/lists
    def gather_text(d):
        texts = []
        if isinstance(d, dict):
            for v in d.values():
                texts.extend(gather_text(v))
        elif isinstance(d, list):
            for i in d:
                texts.extend(gather_text(i))
        elif isinstance(d, str):
            texts.append(d.lower())
        return texts

    for r in records:
        combined_text = " ".join(gather_text(r))
        # Check if all keywords are present
        if all(k in combined_text for k in keywords):
            matches.append(r)

    if not matches:
        return {"message": f"No records found for '{query}'"}

    return {
        "query": query,
        "keywords": keywords,
        "total_matches": len(matches),
        "results": matches
    }
