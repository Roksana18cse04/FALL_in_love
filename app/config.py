import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY")
WEAVIATE_HOST = os.getenv("WEAVIATE_HOST")


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

import cloudinary

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)
import os
import pandas as pd

# Base dir (root of the app folder)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Folder for CSV storage
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)  # ✅ Create data folder if not exists

# CSV file paths
POLICY_CSV = os.path.join(DATA_DIR, "policy_views.csv")
CATEGORY_CSV = os.path.join(DATA_DIR, "category_views.csv")

# Initialize CSVs with headers if not exist
if not os.path.exists(POLICY_CSV):
    pd.DataFrame(columns=["policy_id", "policy_name", "category", "view_count"]).to_csv(POLICY_CSV, index=False)

if not os.path.exists(CATEGORY_CSV):
    pd.DataFrame(columns=["category", "view_count"]).to_csv(CATEGORY_CSV, index=False)
