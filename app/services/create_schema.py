# create schema for Weaviate v4.16.4
from app.services.weaviate_client import client
from weaviate.classes.config import Property, DataType, Configure, VectorDistances, Tokenization


def create_schema():
    """Create PolicyDocuments schema with vectorizer configuration"""
    if not client.is_connected():
        client.connect()
    
    try:
        # Check if collection already exists
        collections = client.collections.list_all()
        if "PolicyDocuments" not in collections:
            client.collections.create(
                name="PolicyDocuments",
                
                # Configure vectorizer - text2vec-openai
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
                        name="title", 
                        data_type=DataType.TEXT,
                        vectorize_property_name=False,
                        tokenization=Tokenization.WORD
                    ),
                    Property(
                        name="summary", 
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
                        name="data", 
                        data_type=DataType.TEXT,
                        vectorize_property_name=False,
                        tokenization=Tokenization.WORD
                    ),
                    Property(
                        name="source", 
                        data_type=DataType.TEXT,
                        vectorize_property_name=False,
                        tokenization=Tokenization.FIELD  # field for exact matching
                    ),
                    Property(name="created_at", data_type=DataType.DATE),
                    Property(name="last_updated", data_type=DataType.DATE)
                ]
            )
            print("Created PolicyDocuments schema with vectorizer.")
        else:
            print("PolicyDocuments schema already exists.")
            
    except Exception as e:
        print(f"Error creating PolicyDocuments schema: {e}")
        raise e
        
    finally:
        if client.is_connected():
            client.close()


if __name__ == "__main__":
    create_schema()
    print("Schema creation script executed.")

    # delete the schema if needed then create_schema function will be commented
    # if not client.is_connected():
    #     client.connect()
    #     client.collections.delete("PolicyDocuments")
    #     print("PolicyDocuments schema deleted.")
    #     client.close()