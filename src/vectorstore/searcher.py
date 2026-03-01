import os
import re
import requests
from pathlib import Path
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

# Load environment variables
load_dotenv()

# ─────────────────────────────────────────────
# SETTINGS
# ─────────────────────────────────────────────
COLLECTION = os.getenv("QDRANT_COLLECTION", "sona_knowledge")
QDRANT_URL = os.getenv("QDRANT_URL", "qdrant_local_db")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OLLAMA_URL = os.getenv("EMBEDDING_API_URL", "http://localhost:11434/api/embeddings")
MODEL_NAME = "nomic-embed-text"

# ─────────────────────────────────────────────
# CONNECT TO QDRANT (DYNAMIC)
# ─────────────────────────────────────────────
if QDRANT_URL == "qdrant_local_db":
    print("🏠 Searcher: Connecting to LOCAL Qdrant...")
    client = QdrantClient(path=QDRANT_URL)
else:
    print(f"☁️ Searcher: Connecting to REMOTE Qdrant...")
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


# ---------------- EMBEDDING ----------------
def embed(text: str):
    # FIX: Use the OLLAMA_URL variable from settings
    r = requests.post(
        OLLAMA_URL,
        json={"model": MODEL_NAME, "prompt": text},
        timeout=60
    )
    r.raise_for_status()
    return r.json()["embedding"]


# ---------------- ENHANCED QUERY PARSER ----------------
def parse_query(q: str):
    q_lower = q.lower()
    categories = ["bcm", "mbc", "sca", "oc", "bc", "sc", "st"]
    
    dept_mapping = {
        "cse": "CSE", "ads": "ADS", "it": "IT", "aml": "AML", "ece": "ECE",
        "eee": "EEE", "mech": "MECH", "civil": "CIVIL", "ft": "FT",
        "computer science": "CSE", "artificial intelligence": "ADS",
        "information technology": "IT", "machine learning": "AML",
        "electronics": "ECE", "electrical": "EEE", "mechanical": "MECH",
        "fashion": "FT"
    }

    dept, cat, year = None, None, None

    # Extract department
    sorted_depts = sorted(dept_mapping.keys(), key=len, reverse=True)
    for dept_pattern in sorted_depts:
        if dept_pattern in q_lower:
            dept = dept_mapping[dept_pattern]
            break

    # Extract category
    for c in categories:
        if re.search(rf"\b{c}\b", q_lower):
            cat = c.upper()
            break

    # Extract year
    year_match = re.search(r"\b(20\d{2}|\d{2})\b", q_lower)
    if year_match:
        year_str = year_match.group(1)
        year = 2000 + int(year_str) if len(year_str) == 2 else int(year_str)

    return dept, cat, year


# ---------------- HYBRID SEARCH ----------------
def search_cutoffs(query: str):
    dept, cat, year = parse_query(query)
    print(f"🔍 Parsed → Dept: {dept}, Cat: {cat}, Year: {year}")

    conditions = []
    if dept: conditions.append(FieldCondition(key="code", match=MatchValue(value=dept)))
    if cat: conditions.append(FieldCondition(key="category", match=MatchValue(value=cat)))
    if year: conditions.append(FieldCondition(key="year", match=MatchValue(value=year)))

    if conditions:
        results = client.query_points(
            collection_name=COLLECTION,
            query=embed(query),
            query_filter=Filter(must=conditions),
            limit=5
        ).points

        if results:
            return "\n".join(format_result(r.payload) for r in results)

    # Fallback to pure vector search if no results found with filters
    results = client.query_points(
        collection_name=COLLECTION,
        query=embed(query),
        limit=5
    ).points

    return "\n".join(format_result(r.payload) for r in results)


# ---------------- FORMAT OUTPUT ----------------
def format_result(p):
    max_v = p.get("max", "N/A")
    min_v = p.get("min", "N/A")
    year = p.get("year", "N/A")
    result = f"{p['department']} ({p['code']}) [{p['category']}] {year} → max {max_v}, min {min_v}"
    if p.get("available_seats"):
        result += f" | {p['available_seats']} seats"
    return result


if __name__ == "__main__":
    print("🎓 SONA COLLEGE SEARCHER READY")
    while True:
        q = input("\nAsk cutoff question (or 'exit'): ").strip()
        if not q or q.lower() == 'exit': break
        print("\n--- RESULT ---")
        print(search_cutoffs(q))