from warnings import filters
from app.services.weaviate_client import get_weaviate_client
from weaviate.classes.query import MetadataQuery, Filter
from fastapi.responses import JSONResponse
from collections import OrderedDict

class_name = "HomeCare"
client = get_weaviate_client()

#  Semantic Search - Text similarity based search
async def semantic_search(query_text: str, limit: int = 5):
    """Search documents based on semantic similarity"""
    try:
        if not client.is_connected():
            client.connect()

        collection = client.collections.get(class_name)

        response = collection.query.near_text(
            query=query_text,
            limit=limit,
            return_metadata=MetadataQuery(distance=True, score=True)
        )

        results = []
        for obj in response.objects:
            results.append({
                #"id": str(obj.uuid),
                "title": obj.properties.get("title"),
                "summary": obj.properties.get("summary"),
                "category": obj.properties.get("category"),
                "source": obj.properties.get("source"),
                "created_at": obj.properties.get("created_at"),
                "distance": obj.metadata.distance,
                "score": obj.metadata.score
            })
        
        return JSONResponse(status_code=200, content={
            "status": "success",
            "query": query_text,
            "total_results": len(results),
            "results": results
        })
        
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e)
        })

#  Get all documents (paginated)
async def get_all_documents(limit: int = 20, offset: int = 0):
    """Get all documents with pagination"""
    client = get_weaviate_client()
    try:
        if not client.is_connected():
            client.connect()
        
        collection = client.collections.get(class_name)
        
        response = collection.query.fetch_objects(
            limit=limit,
            offset=offset
        )
        
        unique_map = OrderedDict()
        for obj in response.objects:
            title = obj.properties.get("title")
            if title not in unique_map:
                unique_map[title] = obj  # only keep first chunk per title

        # Convert to list and apply pagination manually
        unique_list = list(unique_map.values())
        paginated = unique_list[offset:offset + limit]

        results = []
        for obj in paginated:
            results.append({
                "title": obj.properties.get("title"),
                "summary": obj.properties.get("summary"),
                "category": obj.properties.get("category"),
                "source": obj.properties.get("source"),
                "created_at": obj.properties.get("created_at").isoformat() if obj.properties.get("created_at") else None,
                "last_updated": obj.properties.get("last_updated").isoformat() if obj.properties.get("last_updated") else None
            })
        
        return JSONResponse(status_code=200, content={
            "status": "success",
            "total_results": len(results),
            "offset": offset,
            "limit": limit,
            "results": results
        })
        
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e)
        })


# Hybrid search (combines semantic and keyword search)
async def hybrid_search(query_text: str, limit: int = 5, alpha: float = 0.5, offset: int = 0):
    """Hybrid search combining semantic and keyword search"""
    client = get_weaviate_client()
    try:
        if not client.is_connected():
            client.connect()
        
        collection = client.collections.get(class_name)
        
        response = collection.query.hybrid(
            query=query_text,
            alpha=alpha,  # 0.0 = pure keyword, 1.0 = pure semantic
            limit=limit,
            return_metadata=MetadataQuery(score=True)
        )

        unique_map = OrderedDict()
        for obj in response.objects:
            title = obj.properties.get("title")
            if title not in unique_map:
                unique_map[title] = obj  # only keep first chunk per title

        # Convert to list and apply pagination manually
        unique_list = list(unique_map.values())
        paginated = unique_list[offset:offset + limit]

        results = []
        for obj in paginated:
            results.append({
                #"id": str(obj.uuid),
                "title": obj.properties.get("title"),
                "summary": obj.properties.get("summary"),
                "category": obj.properties.get("category"),
                "source": obj.properties.get("source"),
                "score": obj.metadata.score
            })
        
        return JSONResponse(status_code=200, content={
            "status": "success",
            "search_type": "hybrid",
            "query": query_text,
            "alpha": alpha,
            "total_results": len(results),
            "results": results
        })
        
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e)
        })
    
async def hybrid_search_with_category(query_text: str, category: str, limit: int = 5, alpha: float = 0.7, offset: int = 0):
    client = get_weaviate_client()
    try:
        if not client.is_connected():
            client.connect()
        
        collection = client.collections.get(class_name)
        
        response = collection.query.hybrid(
            query=query_text,
            alpha=alpha,
            limit=100,  # Increase limit to allow room for filtering
            return_metadata=MetadataQuery(score=True)
        )

       # Filter manually by category
        filtered = [obj for obj in response.objects if obj.properties.get("category") == category]

        # Ensure unique titles only
        unique_map = OrderedDict()
        for obj in filtered:
            title = obj.properties.get("title")
            if title not in unique_map:
                unique_map[title] = obj

        # Convert to list and paginate
        unique_list = list(unique_map.values())
        paginated = unique_list[offset:offset + limit]

        results = []
        for obj in paginated:
            results.append({
                "title": obj.properties.get("title"),
                "summary": obj.properties.get("summary"),
                "category": obj.properties.get("category"),
                "source": obj.properties.get("source"),
                "score": obj.metadata.score
            })

        return JSONResponse(status_code=200, content={
            "status": "success",
            "query": query_text,
            "category": category,
            "search_type": "hybrid_filtered",
            "results": results
        })
        
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e)
        })

import json
#  Filter by category
async def search_by_category(category: str, limit: int = 10, offset: int = 0):
    """Search documents by specific category"""
    try:
        response = await get_all_documents(limit=limit)
        data = json.loads(response.body.decode())
        print("result----------", data['results'])
        # Filter manually by category
        filtered = [obj for obj in data['results'] if obj.get("category") == category]

        results = []
        for obj in filtered:
            results.append({
                "title": obj.get("title"),
                "summary": obj.get("summary"),
                "category": obj.get("category"),
                "source": obj.get("source"),
                "created_at": obj.get("created_at"),
                "last_updated": obj.get("last_updated") 

            })
        
        return JSONResponse(status_code=200, content={
            "status": "success",
            "category": category,
            "total_results": len(results),
            "results": results
        })
        
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e)
        })


#########################################################################
import weaviate
from weaviate.classes.query import Filter, MetadataQuery

from collections import defaultdict

def _version_number(v):
    """Convert version string like 'v2' or '2' to int for sorting."""
    try:
        if isinstance(v, str) and v.startswith("v"):
            return int(v[1:])
        return int(v)
    except (ValueError, TypeError):
        return 1
    
def pick_latest_per_title(objects):
    grouped = defaultdict(list)
    for obj in objects:
        title = obj.properties.get("title", "")
        grouped[title].append(obj)

    latest = []
    for title, objs in grouped.items():
        best = max(objs, key=lambda o: _version_number(o.properties.get("version")))
        latest.append(best)
    return latest

def efficient_query(query_text: str, category: str, document_type: str,
                    limit: int = 5, alpha: float = 0.5):
    """
    Step 1: Filter objects by metadata (category + document_type)
    Step 2: Pick latest version per title
    Step 3: Do near_text (vector search) only on those UUIDs
    """

    if not client.is_connected():
        client.connect()

    collection = client.collections.get("HomeCare")

    try:
        # --- Step 1: Metadata filter ---
        filtered = collection.query.fetch_objects(
            filters=(
                Filter.by_property("category").equal(category) &
                Filter.by_property("document_type").equal(document_type)
            ),
            limit=9999  # Pull all matching to handle versioning
        )

        if not filtered.objects:
            print("No documents found matching the criteria")
            return []

        print(f"Filtered to {len(filtered.objects)} documents")

        # --- Step 2: Pick latest version per title ---
        latest_objs = pick_latest_per_title(filtered.objects)
        print(f"Selected {len(latest_objs)} latest version documents")

        # --- Step 3: Vector search on latest objects only ---
        uuids = [str(obj.uuid) for obj in latest_objs]
        uuid_filter = Filter.by_id().contains_any(uuids)

        vector_response = collection.query.near_text(
            query=query_text,
            filters=uuid_filter,
            # alpha=alpha,
            limit=limit,
            return_metadata=MetadataQuery(score=True)
        )

        # Print results for debugging
        for i, obj in enumerate(vector_response.objects, 1):
            print(f"{i}. Title: {obj.properties.get('title')}")
            print(f"   Category: {obj.properties.get('category')}")
            print(f"   Document Type: {obj.properties.get('document_type')}")
            print(f"   Content: {obj.properties.get('data', '')[:100]}...")
            print(f"   Version: {obj.properties.get('version', 'v1')}")
            print("-----")

        return vector_response.objects

    except Exception as e:
        print(f"Query error: {e}")
        return []

if __name__ == "__main__":
    try:
        results = efficient_query(
            query_text="i want to know about aged care policy",
            category="privacy_confidentiality_information_governance",
            document_type="policy",
            limit=5
        )
        print(f"\nTotal results: {len(results)}")
    finally:
        client.close()




# if __name__ == "__main__":
#     from weaviate.classes.query import Filter

#     jeopardy = client.collections.use("HomeCare")
#     response = jeopardy.query.fetch_objects(
#         filters=Filter.by_property("category").equal("Aged Care"),
#         limit=3
#     )

#     for o in response.objects:
#         print(o.properties)