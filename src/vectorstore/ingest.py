import os
import json
import time
import requests
from pathlib import Path
from uuid import uuid4
from collections import Counter
from dotenv import load_dotenv

from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

load_dotenv()

# ─────────────────────────────────────────────
# SETTINGS
# ─────────────────────────────────────────────
# IMPORTANT: Added back missing variables
COLLECTION = os.getenv("QDRANT_COLLECTION", "sona_knowledge")
VECTOR_SIZE = 768  # nomic-embed-text size
MODEL_NAME = "nomic-embed-text"
SLEEP = 0.03

QDRANT_URL = os.getenv("QDRANT_URL", "qdrant_local_db")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OLLAMA_URL = os.getenv("EMBEDDING_API_URL", "http://localhost:11434/api/embeddings")

# ─────────────────────────────────────────────
# CONNECT TO QDRANT (DYNAMIC)
# ─────────────────────────────────────────────
# FIX: Removed the redundant 'client = QdrantClient(path="qdrant_local_db")' call 
# that was overriding your logic below.
if QDRANT_URL == "qdrant_local_db":
    print("🏠 Connecting to LOCAL Qdrant (file mode)...")
    client = QdrantClient(path=QDRANT_URL)
else:
    print(f"☁️ Connecting to REMOTE Qdrant at {QDRANT_URL}...")
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

# Rebuild Collection
if client.collection_exists(COLLECTION):
    print(f"⚠️ Collection '{COLLECTION}' exists — rebuilding...")
    client.delete_collection(COLLECTION)

client.create_collection(
    collection_name=COLLECTION,
    vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
)

print("✅ Connected to local Qdrant")


# ─────────────────────────────────────────────
# LOAD JSON (SAFE ROOT PATH)
# ─────────────────────────────────────────────
ROOT = Path.cwd()
json_path = ROOT / "knowledge" / "info.json"

with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

college = data.get("college", "The College")
print(f"✅ JSON loaded — {college}")


# ─────────────────────────────────────────────
# BUILD CUTOFF CHUNKS (MATCHES YOUR JSON)
# ─────────────────────────────────────────────
chunks = []

for dept in data.get("cutoff_data", []):

    dept_name = dept.get("department", "")
    code = dept.get("code", "")
    
    # Iterate through years array
    for year_data in dept.get("years", []):
        
        year = year_data.get("year")
        available_seats = year_data.get("available_seats")
        cutoff_info = year_data.get("cutoff", {})

        for category, values in cutoff_info.items():

            # Skip empty category blocks
            if values is None:
                continue

            max_cut = values.get("max") if values.get("max") is not None else "not available"
            min_cut = values.get("min") if values.get("min") is not None else "not available"

            text = (
                f"{college} cutoff for {dept_name} ({code}) in {year} "
                f"category {category}: maximum {max_cut}, minimum {min_cut}. "
                f"Available seats: {available_seats if available_seats else 'not specified'}."
            )

            chunks.append({
                "text": text,
                "college": college,
                "department": dept_name,
                "code": code,
                "year": year,
                "available_seats": available_seats,
                "category": category,
                "max": max_cut,
                "min": min_cut,
                "type": "cutoff"
            })

print(f"✅ {len(chunks)} cutoff chunks created")

# Show breakdown
counts = Counter(c["category"] for c in chunks)
for cat, n in sorted(counts.items()):
    print(f"     {cat:10} → {n}")


# ─────────────────────────────────────────────
# OLLAMA EMBEDDING WITH RETRY
# ─────────────────────────────────────────────
def embed(text: str, retries: int = 3):

    for attempt in range(retries):
        try:
            r = requests.post(
                OLLAMA_URL,
                json={"model": MODEL_NAME, "prompt": text},
                timeout=60,
            )
            r.raise_for_status()
            return r.json()["embedding"]

        except Exception as e:
            if attempt == retries - 1:
                raise RuntimeError(f"Embedding failed: {e}")
            time.sleep(1)


# ─────────────────────────────────────────────
# CREATE EMBEDDINGS
# ─────────────────────────────────────────────
print("\n🔄 Creating embeddings via Ollama...")

vectors = []
for i, chunk in enumerate(chunks):

    vectors.append(embed(chunk["text"]))
    time.sleep(SLEEP)

    if (i+1) % 10 == 0 or (i+1) == len(chunks):
        print(f"   {i+1}/{len(chunks)} embedded")

print("✅ All embeddings ready")


# ─────────────────────────────────────────────
# STORE INTO QDRANT
# ─────────────────────────────────────────────
print("\n📦 Storing into Qdrant...")

points = [
    PointStruct(
        id=str(uuid4()),
        vector=vectors[i],
        payload=chunks[i],
    )
    for i in range(len(chunks))
]

client.upsert(collection_name=COLLECTION, points=points)

client.close()


# ─────────────────────────────────────────────
# DONE
# ─────────────────────────────────────────────
print(f"""
🎉 INGEST COMPLETE
   Stored vectors : {len(points)}
   Collection     : {COLLECTION}
   Local DB       : qdrant_local_db/
""")