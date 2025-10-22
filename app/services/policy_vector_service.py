"""
Fixed Policy Vector Service with proper error handling and fallback mechanisms
"""

from typing import List, Dict, Optional
from weaviate.classes.query import Filter, MetadataQuery
from app.services.weaviate_client import get_weaviate_client
from weaviate.classes.config import Property, DataType, Configure, VectorDistances


class PolicyVectorService:
    """Service for retrieving super admin laws from PolicyEmbeddings collection."""
    
    def __init__(self, organization_type: str):
        self.client = get_weaviate_client()
        self.COLLECTION_NAME = organization_type
    
    async def ensure_collection_schema(self):
        """
        Ensure collection exists and is configured properly.
        """
        try:
            if not self.client.is_connected():
                self.client.connect()
            
            collections = self.client.collections.list_all()
            
            if self.COLLECTION_NAME not in collections:
                print(f"Creating collection {self.COLLECTION_NAME} with vectorizer...")
                # Create collection with vectorizer
                self.client.collections.create(
                    name=self.COLLECTION_NAME,
                    vectorizer_config=Configure.Vectorizer.text2vec_openai(
                        model="text-embedding-3-small",
                        vectorize_collection_name=False
                    ),
                    vector_index_config=Configure.VectorIndex.hnsw(
                        distance_metric=VectorDistances.COSINE,
                        ef_construction=128,
                        max_connections=64
                    ),
                    properties=[
                        Property(name="law_id", data_type=DataType.TEXT),
                        Property(name="title", data_type=DataType.TEXT),
                        Property(name="text", data_type=DataType.TEXT),
                        Property(name="version", data_type=DataType.TEXT),
                    ]
                )
                print(f"Collection {self.COLLECTION_NAME} created successfully.")
            else:
                print(f"Collection {self.COLLECTION_NAME} already exists.")
                
        except Exception as e:
            print(f"Error ensuring collection schema: {str(e)}")
        finally:
            if self.client.is_connected():
                self.client.close()

    async def get_super_admin_laws_for_generation(
        self, 
        query: str, 
        version: Optional[str] = None, 
        limit: int = 20
    ) -> str:
        """
        Get super admin laws from collection for policy generation.
        Uses fallback to regular fetch if vector search fails.
        
        Args:
            query: Search query to find relevant laws
            version: Specific version to use (None for latest)
            limit: Number of laws to retrieve
            
        Returns:
            Combined law content for policy generation
        """
        await self.ensure_collection_schema()
        
        try:
            if not self.client.is_connected():
                self.client.connect()

            collection = self.client.collections.get(self.COLLECTION_NAME)

            # Build filters
            filters = None
            if version:
                filters = Filter.by_property("version").equal(version)
            
            # Try vector search first
            try:
                print(f"Attempting vector search for query: {query[:50]}...")
                if filters:
                    response = collection.query.near_text(
                        query=query,
                        filters=filters,
                        limit=limit,
                        return_metadata=MetadataQuery(score=True)
                    )
                else:
                    response = collection.query.near_text(
                        query=query,
                        limit=limit,
                        return_metadata=MetadataQuery(score=True)
                    )
                print(f"Vector search successful: {len(response.objects)} results")
                
            except Exception as vector_error:
                print(f"Vector search failed: {str(vector_error)}")
                print("Falling back to regular fetch...")
                # Fallback to regular fetch
                if filters:
                    response = collection.query.fetch_objects(
                        filters=filters,
                        limit=limit
                    )
                else:
                    response = collection.query.fetch_objects(limit=limit)
                print(f"Regular fetch successful: {len(response.objects)} results")
            
            if not response.objects:
                print("No laws found in collection")
                return "No relevant super admin laws found for the given query."
            
            # Combine law contents with safe None handling
            combined_content = []
            for obj in response.objects:
                # Safely get properties with defaults
                title = obj.properties.get("title") or "Unknown Law"
                law_text = obj.properties.get("text") or ""
                law_version = obj.properties.get("version") or "v1"
                
                # Safely get score (might be None if not from vector search)
                score = 0.0
                if hasattr(obj, 'metadata') and obj.metadata and hasattr(obj.metadata, 'score'):
                    score = obj.metadata.score or 0.0
                
                # Format with safe string interpolation
                law_entry = f"""
=== {title} (Version: {law_version}) ===
Relevance Score: {score:.3f}

Content:
{law_text}

---
"""
                combined_content.append(law_entry)
            
            final_content = "\n".join(combined_content)
            print(f"Combined {len(combined_content)} laws into content ({len(final_content)} chars)")
            return final_content
            
        except Exception as e:
            print(f"Error retrieving super admin laws: {str(e)}")
            import traceback
            traceback.print_exc()
            return f"Error retrieving laws: {str(e)}"
            
        finally:
            if self.client.is_connected():
                self.client.close()
    
    async def get_all_laws_from_latest_version(self) -> str:
        """
        Get ALL laws from the latest version in collection.
        """
        await self.ensure_collection_schema()
        
        try:
            if not self.client.is_connected():
                self.client.connect()
            
            collection = self.client.collections.get(self.COLLECTION_NAME)
            
            # Get all objects to find the latest version
            all_results = collection.query.fetch_objects(limit=1000)
            
            if not all_results.objects:
                return "No laws found in collection."
            
            # Find the latest version
            versions = set()
            for obj in all_results.objects:
                version = obj.properties.get("version") or "v1"
                versions.add(version)
            
            # Sort versions and get the latest
            version_list = list(versions)
            version_list.sort(key=lambda x: int(x[1:]) if x.startswith("v") and x[1:].isdigit() else 0, reverse=True)
            latest_version = version_list[0] if version_list else "v1"
            
            print(f"Found latest version: {latest_version}")
            
            # Get all laws from the latest version
            latest_results = collection.query.fetch_objects(
                filters=Filter.by_property("version").equal(latest_version),
                limit=1000
            )
            
            if not latest_results.objects:
                return f"No laws found for latest version {latest_version}."
            
            # Combine all law contents
            combined_content = []
            for obj in latest_results.objects:
                title = obj.properties.get("title") or "Unknown Law"
                law_text = obj.properties.get("text") or ""
                law_version = obj.properties.get("version") or "v1"
                
                combined_content.append(f"""
=== {title} (Version: {law_version}) ===

Content:
{law_text}

---
""")
            
            return "\n".join(combined_content)
            
        except Exception as e:
            print(f"Error retrieving all laws from latest version: {str(e)}")
            import traceback
            traceback.print_exc()
            return f"Error retrieving laws: {str(e)}"
            
        finally:
            if self.client.is_connected():
                self.client.close()

    async def get_available_versions(self) -> List[str]:
        """Get all available versions from collection."""
        await self.ensure_collection_schema()
        
        try:
            if not self.client.is_connected():
                self.client.connect()
            
            collection = self.client.collections.get(self.COLLECTION_NAME)
            
            # Get all objects to extract versions
            results = collection.query.fetch_objects(limit=1000)
            
            versions = set()
            for obj in results.objects:
                version = obj.properties.get("version") or "v1"
                versions.add(version)
            
            # Sort versions
            version_list = list(versions)
            version_list.sort(key=lambda x: int(x[1:]) if x.startswith("v") and x[1:].isdigit() else 0)
            
            return version_list
            
        except Exception as e:
            print(f"Error getting available versions: {str(e)}")
            return []
            
        finally:
            if self.client.is_connected():
                self.client.close()
    
    async def search_laws(
        self, 
        query: str, 
        version: Optional[str] = None, 
        limit: int = 5
    ) -> List[Dict]:
        """Search laws in collection."""
        await self.ensure_collection_schema()
        
        try:
            if not self.client.is_connected():
                self.client.connect()

            collection = self.client.collections.get(self.COLLECTION_NAME)

            # Build filters
            filters = None
            if version:
                filters = Filter.by_property("version").equal(version)
            
            # Try vector search first
            try:
                if filters:
                    response = collection.query.near_text(
                        query=query,
                        filters=filters,
                        limit=limit,
                        return_metadata=MetadataQuery(score=True)
                    )
                else:
                    response = collection.query.near_text(
                        query=query,
                        limit=limit,
                        return_metadata=MetadataQuery(score=True)
                    )
            except Exception as vector_error:
                print(f"Vector search failed, using regular search: {vector_error}")
                # Fallback to regular fetch
                if filters:
                    response = collection.query.fetch_objects(
                        filters=filters,
                        limit=limit
                    )
                else:
                    response = collection.query.fetch_objects(limit=limit)
            
            laws = []
            for obj in response.objects:
                text = obj.properties.get("text", "")
                text_preview = text[:500] + "..." if len(text) > 500 else text
                
                # Safely get score
                score = 0.0
                if hasattr(obj, 'metadata') and obj.metadata and hasattr(obj.metadata, 'score'):
                    score = obj.metadata.score or 0.0
                
                laws.append({
                    "law_id": obj.properties.get("law_id") or "",
                    "title": obj.properties.get("title") or "Unknown Law",
                    "text": text_preview,
                    "version": obj.properties.get("version") or "v1",
                    "score": score
                })
            
            return laws
            
        except Exception as e:
            print(f"Error searching laws: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
            
        finally:
            if self.client.is_connected():
                self.client.close()