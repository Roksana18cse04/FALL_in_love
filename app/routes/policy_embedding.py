from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import PlainTextResponse
from weaviate.classes.query import Filter
from app.services.extract_content import extract_content_from_pdf
from app.services.weaviate_client import get_weaviate_client
from app.services.embedding_service import embed_text_openai
import uuid
import re

router = APIRouter()

def get_version_from_filename(filename: str) -> str:
    """Extract version from filename like 'policy_v2.pdf' -> 'v2'. Defaults to 'v1'."""
    match = re.search(r"_v(\d+)", filename or "")
    if match:
        return f"v{match.group(1)}"
    return "v1"

def compute_next_version(collection, title: str) -> str:
    """Return the next version for a given title by inspecting existing objects."""
    try:
        results = collection.query.fetch_objects(
            where={
                "path": ["title"],
                "operator": "Equal",
                "valueText": title,
            }
        )
        versions = []
        for obj in getattr(results, "objects", []) or []:
            v = (obj.properties or {}).get("version", "v1")
            try:
                if isinstance(v, str) and v.startswith("v"):
                    versions.append(int(v[1:]))
                else:
                    versions.append(int(v))
            except Exception:
                versions.append(1)
        if not versions:
            return "v1"
        return f"v{max(versions) + 1}"
    except Exception:
        # Fallback if query fails
        return "v1"

def compute_global_next_version(collection) -> str:
    """Return next version number irrespective of title/filename.

    Looks at all objects in the collection, finds the highest version value,
    and returns v{max+1}. If no objects or version missing, starts at v1.
    """
    try:
        results = collection.query.fetch_objects()
        max_version = 0
        for obj in getattr(results, "objects", []) or []:
            v = (obj.properties or {}).get("version")
            if not v:
                continue
            try:
                if isinstance(v, str) and v.startswith("v"):
                    max_version = max(max_version, int(v[1:]))
                else:
                    max_version = max(max_version, int(v))
            except Exception:
                continue
        return f"v{max_version + 1 if max_version > 0 else 1}"
    except Exception:
        return "v1"

@router.post("/admin/upload-law")
async def upload_policy_pdf(file: UploadFile = File(...)):
    # Extract text from PDF
    text, title = await extract_content_from_pdf(file)
    if not text:
        raise HTTPException(status_code=400, detail="Could not extract text from PDF.")
    # Embed text
    embedding = await embed_text_openai(text)
    # Save to Weaviate
    client = get_weaviate_client()
    # Check if collection exists, create if not
    collections = client.collections.list_all()
    if "PolicyEmbeddings" not in collections:
        from weaviate.classes.config import Property, DataType, Configure, VectorDistances, Tokenization
        client.collections.create(
            name="PolicyEmbeddings",
            vectorizer_config=Configure.Vectorizer.none(),
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
    # Ensure existing collection has the 'version' property
    collection = client.collections.get("PolicyEmbeddings")
    try:
        schema = collection.schema.get()
        prop_names = [p.get("name") for p in schema.get("properties", [])]
        if "version" not in prop_names:
            from weaviate.classes.config import Property, DataType
            collection.schema.add_property(Property(name="version", data_type=DataType.TEXT))
    except Exception:
        # Schema fetch/addition best-effort; proceed with insert
        pass
    obj_id = str(uuid.uuid4())
    # Decide version: global auto-increment regardless of title/filename
    version_value = compute_global_next_version(collection)
    collection.data.insert({
        "policy_id": obj_id,
        "filename": file.filename,
        "title": title,
        "text": text,
        "version": version_value,
        "embedding": embedding
    }, vector=embedding)
    return {"status": "success", "policy_id": obj_id}

@router.get("/admin/policy-text")
async def get_policy_text(version: str | None = Query(default=None), as_file: bool = Query(default=False)):
    """Fetch policy text by version. If version is omitted, return latest version.

    - version: e.g., 'v3'. If None, the object with the highest version is returned.
    - as_file: when true, returns a text/plain response with Content-Disposition.
    """
    client = get_weaviate_client()
    try:
        collection = client.collections.get("PolicyEmbeddings")

        def version_to_int(v: str) -> int:
            try:
                if isinstance(v, str) and v.startswith("v"):
                    return int(v[1:])
                return int(v)
            except Exception:
                return 1

        if version:
            results = collection.query.fetch_objects(
                filters=Filter.by_property("version").equal(version)
            )
            objs = getattr(results, "objects", []) or []
            if not objs:
                raise HTTPException(status_code=404, detail=f"No policy found for version {version}")
            obj = objs[-1]
        else:
            results = collection.query.fetch_objects()
            objs = getattr(results, "objects", []) or []
            if not objs:
                raise HTTPException(status_code=404, detail="No policies found")
            obj = max(objs, key=lambda o: version_to_int((o.properties or {}).get("version", "v1")))

        props = obj.properties or {}
        text_value = props.get("text", "")
        if as_file:
            filename = props.get("filename") or f"policy_{props.get('version','v1')}.txt"
            headers = {"Content-Disposition": f"attachment; filename=\"{filename}\""}
            return PlainTextResponse(content=text_value, headers=headers)
        return {
            "policy_id": props.get("policy_id"),
            "filename": props.get("filename"),
            "title": props.get("title"),
            "version": props.get("version"),
            "text": text_value,
        }
    finally:
        try:
            client.close()
        except Exception:
            pass
