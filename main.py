from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import requests
from fuzzywuzzy import fuzz
import re
from config import BASE_URL, RECORDS_ENDPOINT, AUTH_HEADERS

app = FastAPI(
    title="Lesson Learnt Semantic Search API",
    description="Search lessons learnt by typing natural human queries like 'Show me lessons learnt in construction sector'",
    version="1.0.0"
)

# Allow frontend apps or external clients to access the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------- Core Logic ---------------------- #
def fetch_all_records():
    """Fetch all lessons from the database API."""
    url = f"{BASE_URL}{RECORDS_ENDPOINT}"
    try:
        response = requests.get(url, headers=AUTH_HEADERS)
        response.raise_for_status()
        data = response.json().get("data", {}).get("result", [])
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return []


def preprocess_query(query: str):
    """Extract useful search terms from natural language."""
    query = query.lower()
    stopwords = [
        "show", "me", "all", "tell", "the", "lessons", "learnt", "about", "in",
        "for", "risk", "lesson", "project", "sector", "portfolio"
    ]
    words = [w for w in re.findall(r'\w+', query) if w not in stopwords]
    return words


def semantic_search(records, query: str):
    """Perform a fuzzy + semantic search over type, lesson, sector, and portfolio."""
    keywords = preprocess_query(query)
    matches = []

    for r in records:
        type_desc = r.get("typeDescription", "")
        lesson = r.get("lessonLearnt", "")
        title = r.get("title", "")
        details = r.get("details", "")
        transaction = str(r.get("consultantTransaction", {}).get("transactionName", ""))
        portfolio = str(r.get("consultantTransaction", {}).get("portfolioName", ""))
        sector = str(r.get("consultantTransaction", {}).get("sector", ""))

        combined_text = " ".join([
            type_desc, lesson, title, details,
            transaction, portfolio, sector
        ]).lower()

        total_score = sum(fuzz.partial_ratio(word, combined_text) for word in keywords)
        avg_score = total_score / max(len(keywords), 1)

        if avg_score > 60:
            matches.append({
                "title": title,
                "lesson": lesson,
                "risk_type": type_desc,
                "transaction": transaction,
                "portfolio": portfolio,
                "sector": sector,
                "score": round(avg_score, 2)
            })

    # Sort results by score (most relevant first)
    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches


# ---------------------- API Routes ---------------------- #

@app.get("/")
def home():
    return {
        "message": "Welcome to the Lesson Learnt Search",
        "example_query": "/search?query=lessons+learnt+in+construction+sector"
    }


@app.get("/search")
def search_lessons(query: str = Query(..., description="Type your natural language query")):
    """Search endpoint that accepts human-like queries."""
    records = fetch_all_records()
    if not records:
        return {"error": "No records found from API."}

    results = semantic_search(records, query)
    if not results:
        return {"message": f"No matching lessons found for '{query}'"}

    return {
        "query": query,
        "count": len(results),
        "results": results[:20] 
    }
