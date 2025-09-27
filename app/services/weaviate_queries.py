from app.services.weaviate_client import client
from weaviate.classes.query import MetadataQuery, Filter
from fastapi.responses import JSONResponse
from collections import OrderedDict

class_name = "HomeCare"

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

def query(query_text: str, category: str, document_type: str, summary: str, limit: int = 5, alpha: float = 0.5):
    # Client connection check
    if not client.is_connected():
        client.connect()
    
    collection = client.collections.get("HomeCare")

    # v4 এর Filter class ব্যবহার করে
    filters = Filter.all_of([
        Filter.by_property("category").equal(category),
        Filter.by_property("document_type").equal(document_type)
    ])

    # MetadataQuery for return metadata
    metadata_query = MetadataQuery(score=True, distance=True)

    try:
        response = collection.query.hybrid(
            query=query_text,
            alpha=alpha,
            limit=limit,
            where_filter=filters, 
            return_metadata=metadata_query
        )

        # Results display
        for obj in response.objects:
            print("Title:", obj.properties.get("title", "N/A"))
            print("Category:", obj.properties.get("category", "N/A"))
            print("Document Type:", obj.properties.get("document_type", "N/A"))
            print("Score:", getattr(obj.metadata, 'score', 'N/A'))
            print("Distance:", getattr(obj.metadata, 'distance', 'N/A'))
            print("-----")
            
        return response.objects
        
    except Exception as e:
        print(f"Query error: {e}")
        return []

if __name__ == "__main__":
    try:
        results = query(
            query_text="i want to know about aged care policy",
            category="Aged Care",
            document_type="policy", 
            summary="Sample summary",
            limit=5,
            alpha=0.5
        )
        
        print(f"\nFound {len(results)} results")
        
    finally:
        client.close() 