# create schema for Weaviate
from app.services.weaviate_client import client
from weaviate.classes.config import Property, DataType, Configure


def create_schema():
    if not client.is_connected():
        client.connect()
    try:
        if "PolicyDocuments" not in client.collections.list_all():
            client.collections.create(
                name="PolicyDocuments",
                properties=[
                    Property(name="title", data_type=DataType.TEXT),
                    Property(name="summary", data_type=DataType.TEXT),
                    Property(name="category", data_type=DataType.TEXT),
                    Property(name="data", data_type=DataType.TEXT),
                    Property(name="source", data_type=DataType.TEXT),
                    Property(name="created_at", data_type=DataType.DATE),
                    Property(name="last_updated", data_type=DataType.DATE)

                ]
            )
            print("Created PolicyDocuments schema.")
        else:
            print("PolicyDocuments schema already exists.")
    except Exception as e:
        print(f"Error creating PolicyDocuments schema: {e}")

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