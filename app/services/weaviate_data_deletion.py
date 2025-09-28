from app.services.weaviate_client import get_weaviate_client
from weaviate.classes.query import Filter

async def delete_weaviate_data(organization: str, category: str, document_type: str, filename: str, version: str):
    client = get_weaviate_client()
    try:
        if not client.is_connected():
            client.connect()

        collection = client.collections.use(organization)

        # Build combined filter
        metadata_filter = (
            Filter.by_property("category").equal(category) &
            Filter.by_property("document_type").equal(document_type) &
            Filter.by_property("title").equal(filename) &
            Filter.by_property("version").equal(version)
        )

        # Fetch matching objects
        collection.data.delete_many(
            where=metadata_filter
        )

        return {
            "status": "success",
            "message": f"Deleted document(s) with title '{filename}' and version '{version}'."
        }
    
    except Exception as e:
        print(f"Error during deletion: {e}")
        return {"status": "error", "message": str(e)}
    
    finally:
        if client.is_connected():
            client.close()


if __name__ == "__main__":
    import asyncio
    # Example usage
    response = asyncio.run(delete_weaviate_data(
        organization="HomeCare",
        category="privacy_confidentiality_information_governance",
        document_type="policy",
        filename="Provider registration policy",
        version="v1"
    ) )
    print("Deletion response:", response)