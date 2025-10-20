import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY")
WEAVIATE_HOST = os.getenv("WEAVIATE_HOST")

DROPBOX_APP_KEY = os.getenv("DROPBOX_APP_KEY")
DROPBOX_APP_SECRET = os.getenv("DROPBOX_APP_SECRET")
DROPBOX_REFRESH_TOKEN = os.getenv("DROPBOX_REFRESH_TOKEN")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BASE_URL = "https://jahidtestmysite.pythonanywhere.com"
BACKEND_HISTORY_URL = f"{BASE_URL}/ai/ChatHistory/"
BACKEND_TOKEN_COUNT_URL = f"{BASE_URL}/ai/TokenCount/"
BACKEND_DOC_READ_COUNT_URL = f"{BASE_URL}/documents/Count/"

GLOBAL_ORG = "GlobalLaw"
 
