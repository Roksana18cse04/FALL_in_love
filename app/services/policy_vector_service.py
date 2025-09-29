"""
Policy Vector Service for retrieving super admin laws from existing PolicyEmbeddings collection
and using them for policy generation with strict adherence.
"""

from typing import List, Dict, Optional
from weaviate.classes.query import Filter, MetadataQuery
from app.services.weaviate_client import get_weaviate_client
from weaviate.classes.config import Property, DataType, Configure, VectorDistances, Tokenization


class PolicyVectorService:
    """Service for retrieving super admin laws from PolicyEmbeddings collection."""
    
    COLLECTION_NAME = "PolicyEmbeddings"
    
    def __init__(self):
        self.client = get_weaviate_client()
    
    async def ensure_collection_schema(self):
        """
        Ensure PolicyEmbeddings collection exists and is configured for semantic search (vectorizer enabled).
        If not, create or update it with text2vec-openai vectorizer.
        """
        try:
            if not self.client.is_connected():
                self.client.connect()
            collections = self.client.collections.list_all()
            if self.COLLECTION_NAME not in collections:
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
                        Property(name="policy_id", data_type=DataType.TEXT),
                        Property(name="filename", data_type=DataType.TEXT),
                        Property(name="title", data_type=DataType.TEXT),
                        Property(name="text", data_type=DataType.TEXT),
                        Property(name="version", data_type=DataType.TEXT),
                        Property(name="embedding", data_type=DataType.NUMBER_ARRAY)
                    ]
                )
            else:
                # Check if vectorizer is set, if not, update schema (Weaviate may not allow direct update, so log warning)
                collection = self.client.collections.get(self.COLLECTION_NAME)
                schema = collection.schema.get()
                if schema.get("vectorizer", "none").lower() == "none":
                    print("WARNING: PolicyEmbeddings collection exists but has no vectorizer. Please recreate the collection with a vectorizer for semantic search.")
        except Exception as e:
            print(f"Error ensuring PolicyEmbeddings schema: {str(e)}")
        finally:
            if self.client.is_connected():
                self.client.close()

    async def get_super_admin_laws_for_generation(
        self, 
        query: str, 
        version: Optional[str] = None, 
        limit: int = 20
    ) -> str:
        await self.ensure_collection_schema()
        """
        Get super admin laws from PolicyEmbeddings collection for policy generation.
        
        Args:
            query: Search query to find relevant laws
            version: Specific version to use (None for latest)
            limit: Number of laws to retrieve
            
        Returns:
            Combined law content for policy generation
        """
        try:
            if not self.client.is_connected():
                self.client.connect()
            
            collection = self.client.collections.get(self.COLLECTION_NAME)
            
            # Build filters
            filters = []
            if version:
                filters.append(Filter.by_property("version").equal(version))
            
            # Combine filters
            combined_filter = None
            if filters:
                combined_filter = filters[0]
                for f in filters[1:]:
                    combined_filter = combined_filter & f
            
            # Perform vector search
            if combined_filter:
                response = collection.query.near_text(
                    query=query,
                    filters=combined_filter,
                    limit=limit,
                    return_metadata=MetadataQuery(score=True)
                )
            else:
                response = collection.query.near_text(
                    query=query,
                    limit=limit,
                    return_metadata=MetadataQuery(score=True)
                )
            
            if not response.objects:
                return "No relevant super admin laws found for the given query."
            
            # Combine law contents
            combined_content = []
            for obj in response.objects:
                title = obj.properties.get("title", "Unknown Law")
                law_text = obj.properties.get("text", "")
                law_version = obj.properties.get("version", "v1")
                score = obj.metadata.score if obj.metadata else 0.0
                
                combined_content.append(f"""
=== {title} (Version: {law_version}) ===
Relevance Score: {score:.3f}

Content:
{law_text}

---
""")
            
            return "\n".join(combined_content)
            
        except Exception as e:
            print(f"Error retrieving super admin laws: {str(e)}")
            return "Error retrieving super admin laws from vector database."
        finally:
            if self.client.is_connected():
                self.client.close()
    
    async def get_all_laws_from_latest_version(self) -> str:
        """
        Get ALL laws from the latest version in PolicyEmbeddings collection.
        This ensures complete coverage of all available laws.
        """
        await self.ensure_collection_schema()
        try:
            if not self.client.is_connected():
                self.client.connect()
            
            collection = self.client.collections.get(self.COLLECTION_NAME)
            
            # Get all objects to find the latest version
            all_results = collection.query.fetch_objects(limit=1000)
            
            if not all_results.objects:
                return "No laws found in PolicyEmbeddings collection."
            
            # Find the latest version
            versions = set()
            for obj in all_results.objects:
                version = obj.properties.get("version", "v1")
                versions.add(version)
            
            # Sort versions and get the latest
            version_list = list(versions)
            version_list.sort(key=lambda x: int(x[1:]) if x.startswith("v") else int(x), reverse=True)
            latest_version = version_list[0] if version_list else "v1"
            
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
                title = obj.properties.get("title", "Unknown Law")
                law_text = obj.properties.get("text", "")
                law_version = obj.properties.get("version", "v1")
                
                combined_content.append(f"""
=== {title} (Version: {law_version}) ===

Content:
{law_text}

---
""")
            
            return "\n".join(combined_content)
            
        except Exception as e:
            print(f"Error retrieving all laws from latest version: {str(e)}")
            return "Error retrieving all laws from latest version."
        finally:
            if self.client.is_connected():
                self.client.close()

    async def get_available_versions(self) -> List[str]:
        """Get all available versions from PolicyEmbeddings collection."""
        await self.ensure_collection_schema()
        try:
            if not self.client.is_connected():
                self.client.connect()
            
            collection = self.client.collections.get(self.COLLECTION_NAME)
            
            # Get all objects to extract versions
            results = collection.query.fetch_objects(limit=1000)
            
            versions = set()
            for obj in results.objects:
                version = obj.properties.get("version", "v1")
                versions.add(version)
            
            # Sort versions
            version_list = list(versions)
            version_list.sort(key=lambda x: int(x[1:]) if x.startswith("v") else int(x))
            
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
        """Search laws in PolicyEmbeddings collection."""
        await self.ensure_collection_schema()
        try:
            if not self.client.is_connected():
                self.client.connect()
            
            collection = self.client.collections.get(self.COLLECTION_NAME)
            
            # Build filters
            filters = []
            if version:
                filters.append(Filter.by_property("version").equal(version))
            
            # Combine filters
            combined_filter = None
            if filters:
                combined_filter = filters[0]
                for f in filters[1:]:
                    combined_filter = combined_filter & f
            
            # Perform vector search
            if combined_filter:
                response = collection.query.near_text(
                    query=query,
                    filters=combined_filter,
                    limit=limit,
                    return_metadata=MetadataQuery(score=True)
                )
            else:
                response = collection.query.near_text(
                    query=query,
                    limit=limit,
                    return_metadata=MetadataQuery(score=True)
                )
            
            laws = []
            for obj in response.objects:
                laws.append({
                    "policy_id": obj.properties.get("policy_id"),
                    "title": obj.properties.get("title"),
                    "text": obj.properties.get("text", "")[:500] + "..." if len(obj.properties.get("text", "")) > 500 else obj.properties.get("text", ""),
                    "version": obj.properties.get("version"),
                    "filename": obj.properties.get("filename"),
                    "score": obj.metadata.score if obj.metadata else 0.0
                })
            
            return laws
            
        except Exception as e:
            print(f"Error searching laws: {str(e)}")
            return []
        finally:
            if self.client.is_connected():
                self.client.close()


# Global instance
policy_vector_service = PolicyVectorService()
