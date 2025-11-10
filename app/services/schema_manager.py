
# create schema for Weaviate v4.16.4
from app.services.weaviate_client import get_weaviate_client
from weaviate.classes.config import Property, DataType, Configure, VectorDistances, Tokenization


async def create_schema(organization: str):
    """Create PolicyDocuments schema with vectorizer configuration"""

    client = get_weaviate_client()
    try:
        if not client.is_connected():
            client.connect()

        # Check if collection already exists
        if client.collections.exists(organization):
            print(f"{organization} schema already exists.")
            return {"status": "exists", "message": f"Collection '{organization}' already exists."}
        
        else:
            client.collections.create(
                name=organization,
                # vector_config=Configure.Vectorizer.text2vec_openai(
                #     model="text-embedding-3-small",
                #     vectorize_collection_name=False,
                #     vector_index_config=Configure.VectorIndex.hnsw(
                #         distance_metric=VectorDistances.COSINE,
                #         ef_construction=128,
                #         max_connections=64
                #     )

                # ------------Configure vectorizer - text2vec-openai
                vectorizer_config=Configure.Vectorizer.text2vec_openai(
                    model="text-embedding-3-small",  # Using available model
                    vectorize_collection_name=False
                ),
                # Configure vector index settings
                vector_index_config=Configure.VectorIndex.hnsw(
                    distance_metric=VectorDistances.COSINE,
                    ef_construction=128,
                    max_connections=64

                ),
                properties=[
                    Property(
                        name="document_id",
                        data_type=DataType.TEXT,
                        vectorize_property_name=False,
                        tokenization=Tokenization.FIELD
                    ),
                    Property(
                        name="document_type",
                        data_type=DataType.TEXT,
                        vectorize_property_name=False,
                        tokenization=Tokenization.FIELD
                    ),
                    Property(
                        name="title", 
                        data_type=DataType.TEXT,
                        vectorize_property_name=False,
                        tokenization=Tokenization.WORD
                    ),
                    Property(
                        name="category", 
                        data_type=DataType.TEXT,
                        vectorize_property_name=False,
                        tokenization=Tokenization.WORD
                    ),
                    Property(
                        name="version_id",
                        data_type=DataType.TEXT,
                        vectorize_property_name=False,
                        tokenization=Tokenization.WORD
                    ),
                    Property(
                        name="version_number",
                        data_type=DataType.INT,
                        vectorize_property_name=False
                    ),
                    Property(
                        name="data", 
                        data_type=DataType.TEXT,
                        vectorize_property_name=False,
                        tokenization=Tokenization.WORD
                    ),
                    Property(name="created_at", data_type=DataType.DATE),
                    Property(name="last_updated", data_type=DataType.DATE)
                ]
            )
            print(f"Created {organization} schema with vectorizer.")
            return {"status": "created", "message": f"Collection '{organization}' created successfully."}

    except Exception as e:
        print(f"Error creating {organization} schema----------: {e}")
        raise e
        
    finally:
        if client.is_connected():
            client.close()

async def delete_schema(organization: str):
    print("Deleting schema...")
    client = get_weaviate_client()
    try:
        if not client.is_connected():
            client.connect()

        existing = client.collections.list_all()
        if organization not in existing:
            print(f"{organization} schema does not exist.")
            return {
                "status": "not_found",
                "message": f"Collection '{organization}' does not exist."
            }

        client.collections.delete(organization)
        print(f"{organization} schema deleted.")
        return {
            "status": "deleted",
            "message": f"Collection '{organization}' deleted successfully."
        }

    except Exception as e:
        print(f"Error deleting {organization} schema: {e}")
        raise e
    finally:
        if client.is_connected():
            client.close()

    