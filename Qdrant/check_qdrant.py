import sys
import os
from collections import Counter
from qdrant_client import QdrantClient

# Add current directory to path so we can import src.config
sys.path.append(os.getcwd())

try:
    from src import config
except ImportError as e:
    print(f"Error importing config: {e}")
    sys.exit(1)

client = QdrantClient(
    url=config.QDRANT_URL,
    api_key=config.QDRANT_API_KEY,
    port=config.QDRANT_PORT,
)

collections_to_check = [
    ("Dense", config.COLLECTION_NAME),
    ("Hybrid", config.COLLECTION_NAME_HYBRID)
]

print("--- Collection Info ---")
for label, coll_name in collections_to_check:
    try:
        info = client.get_collection(collection_name=coll_name)
        print(f"{label} Collection ({coll_name}): {info.points_count} points")
    except Exception as e:
        print(f"{label} Collection ({coll_name}): Not found or error: {e}")

print("\n--- Scroll Analysis (rag_documents) ---")
target_coll = config.COLLECTION_NAME # which is rag_documents by default
try:
    # Scroll first 1000 points
    points, _ = client.scroll(
        collection_name=target_coll,
        limit=1000,
        with_payload=True,
        with_vectors=False
    )
    
    with_source = 0
    without_source = 0
    sources = Counter()
    
    for p in points:
        payload = p.payload or {}
        source = payload.get("source_file")
        if source:
            with_source += 1
            sources[source] += 1
        else:
            without_source += 1
            
    print(f"Total points scrolled: {len(points)}")
    print(f"Points with 'source_file': {with_source}")
    print(f"Points without 'source_file': {without_source}")
    
    if sources:
        print("\nPoints per source_file:")
        for src_file, count in sources.items():
            print(f"- {src_file}: {count}")
            
except Exception as e:
    print(f"Error scrolling {target_coll}: {e}")

