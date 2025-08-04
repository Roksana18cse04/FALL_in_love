from app.services.weaviate_client import client
from weaviate.classes.query import MetadataQuery, Filter
from fastapi.responses import JSONResponse

class_name = "PolicyDocuments"

# 1. Semantic Search - Text similarity based search
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
                "id": str(obj.uuid),
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

# 2. Filter by category
async def search_by_category(category: str, limit: int = 10):
    """Search documents by specific category"""
    try:
        if not client.is_connected():
            client.connect()
        
        collection = client.collections.get(class_name)
        
        response = collection.query.fetch_objects(
            where=Filter.by_property("category").equal(category),
            limit=limit
        )
        
        results = []
        for obj in response.objects:
            results.append({
                "id": str(obj.uuid),
                "title": obj.properties.get("title"),
                "summary": obj.properties.get("summary"),
                "category": obj.properties.get("category"),
                "source": obj.properties.get("source"),
                "created_at": obj.properties.get("created_at")
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

# 4. Get all documents (paginated)
async def get_all_documents(limit: int = 20, offset: int = 0):
    """Get all documents with pagination"""
    try:
        if not client.is_connected():
            client.connect()
        
        collection = client.collections.get(class_name)
        
        response = collection.query.fetch_objects(
            limit=limit,
            offset=offset
        )
        
        results = []
        for obj in response.objects:
            results.append({
                "id": str(obj.uuid),
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


# 7. Hybrid search (combines semantic and keyword search)
async def hybrid_search(query_text: str, limit: int = 5, alpha: float = 0.5):
    """Hybrid search combining semantic and keyword search"""
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
        
        results = []
        for obj in response.objects:
            results.append({
                "id": str(obj.uuid),
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
    
async def hybrid_search_with_category(query_text: str, category: str, limit: int = 5, alpha: float = 0.7):
    try:
        if not client.is_connected():
            client.connect()
        
        collection = client.collections.get(class_name)
        
        response = collection.query.hybrid(
            query=query_text,
            alpha=alpha,
            limit=limit,
            where=Filter.by_property("category").equal(category),
            return_metadata=MetadataQuery(score=True)
        )
        
        results = []
        for obj in response.objects:
            results.append({
                "id": str(obj.uuid),
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
