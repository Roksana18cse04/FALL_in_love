"""
Simple Policy Generation Route - Takes only title and context as input
Uses existing PolicyEmbeddings collection in Weaviate for super admin laws
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from app.services.policy_llm import generate_policy_with_vector_laws
from app.services.policy_vector_service import policy_vector_service

router = APIRouter(prefix="/policy", tags=["Policy Generation"])


class SimplePolicyRequest(BaseModel):
    title: str
    context: str
    version: Optional[str] = None


@router.post("/generate")
async def generate_policy(request: SimplePolicyRequest):
    """
    Generate a policy using super admin laws from the existing PolicyEmbeddings collection.
    
    This endpoint:
    - Takes only title and context as required inputs
    - Retrieves relevant super admin laws from Weaviate vector database
    - Generates policy with strict adherence to legal frameworks
    - Supports optional version specification
    """
    try:
        result = await generate_policy_with_vector_laws(
            title=request.title,
            context=request.context,
            version=request.version  # None means latest version
        )
        
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        
        return JSONResponse(content=result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating policy: {str(e)}")


@router.get("/available-versions")
async def get_available_versions():
    """
    Get all available versions from the PolicyEmbeddings collection.
    """
    try:
        versions = await policy_vector_service.get_available_versions()
        return JSONResponse(content={
            "status": "success",
            "available_versions": versions,
            "total_versions": len(versions)
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting available versions: {str(e)}")


@router.get("/search-laws")
async def search_laws(
    query: str = Query(..., description="Search query for relevant laws"),
    version: Optional[str] = Query(default=None, description="Filter by specific version"),
    limit: int = Query(default=5, description="Number of laws to return")
):
    """
    Search for relevant super admin laws before generating policies.
    """
    try:
        laws = await policy_vector_service.search_laws(
            query=query,
            version=version,
            limit=limit
        )
        
        return JSONResponse(content={
            "status": "success",
            "query": query,
            "version": version,
            "total_results": len(laws),
            "laws": laws
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching laws: {str(e)}")


@router.get("/health")
async def health_check():
    """
    Health check endpoint for policy generation service.
    """
    try:
        # Test connection to vector database
        versions = await policy_vector_service.get_available_versions()
        
        return JSONResponse(content={
            "status": "healthy",
            "service": "policy-generation",
            "vector_database": "connected",
            "available_versions": len(versions),
            "collection": "PolicyEmbeddings"
        })
    except Exception as e:
        return JSONResponse(content={
            "status": "unhealthy",
            "service": "policy-generation",
            "error": str(e)
        }, status_code=500)
