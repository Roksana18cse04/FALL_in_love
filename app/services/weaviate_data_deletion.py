from app.services.weaviate_client import get_weaviate_client
from weaviate.classes.query import Filter
from app.services.s3_manager import S3Manager
from app.utils.object_key_parser import parse_object_key


async def delete_weaviate_data(
    organization: str,
    document_id: str,
    version_id: str
):
    client = get_weaviate_client()
    try:
        if not client.is_connected():
            client.connect()

        collection = client.collections.use(organization)

        # Build combined filter
        metadata_filter = (
            Filter.by_property("document_id").equal(document_id)
            & Filter.by_property("version_id").equal(version_id)
        )

        # Perform deletion and capture result
        delete_result = collection.data.delete_many(where=metadata_filter)
        print("delete_result:", delete_result)

        # Safely get count of deleted objects
        deleted_count = (
            getattr(delete_result, "objects_deleted", None)
            or getattr(delete_result, "matches", 0)
            or 0
        )

        # Handle if no items were deleted
        if deleted_count == 0:
            return {
                "status": "not_found",
                "message": f"No document found with document_id '{document_id}' and version '{version_id}'."
            }

        # # Delete from S3 if present
        # try:
        #     s3 = S3Manager()
        #     object_key = f"AI/{document_type}/{category}/{title}"
        #     s3.delete_document(s3version_id, object_key)
        # except Exception as s3_err:
        #     print(f"Warning: S3 deletion failed - {s3_err}")

        return {
            "status": "success",
            "message": f"Deleted {deleted_count} document(s) with document_id '{document_id}' and version '{version_id}'."
        }

    except Exception as e:
        print(f"Error during deletion: {e}")
        return {"status": "error", "message": str(e)}

    finally:
        if client.is_connected():
            client.close()

