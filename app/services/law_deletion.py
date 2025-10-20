from app.services.weaviate_client import get_weaviate_client
from weaviate.classes.query import Filter
from app.config import GLOBAL_ORG



async def delete_weaviate_law(version: str, filename: str):
    client = get_weaviate_client()
    try:
        if not client.is_connected():
            client.connect()

        collection = client.collections.use(GLOBAL_ORG)

        # Build combined filter
        metadata_filter = (
            Filter.by_property("title").equal(filename) &
            Filter.by_property("version").equal(version)
        )

        print("meta filter-----------", metadata_filter)

        # Perform deletion and capture result
        delete_result = collection.data.delete_many(where=metadata_filter)
        print("delete_result-----------", delete_result)

        # Depending on SDK, result may look like {'matches': x, 'limit': y, 'objects_deleted': z}
        deleted_count = getattr(delete_result, "objects_deleted", None) or getattr(delete_result, "matches", 0)

        if deleted_count > 0:
            return {
                "status": "success",
                "message": f"Deleted {deleted_count} document(s) with title '{filename}' and version '{version}'."
            }
        else:
            return {
                "status": "not_found",
                "message": f"No document found for title '{filename}' and version '{version}'."
            }

    except Exception as e:
        print(f"Error during deletion: {e}")
        return {"status": "error", "message": str(e)}
    
    finally:
        if client.is_connected():
            client.close()
