import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY")
WEAVIATE_HOST = os.getenv("WEAVIATE_HOST")

DROPBOX_API_KEY = os.getenv("DROPBOX_API_KEY")


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

