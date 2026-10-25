import os
from dotenv import load_dotenv
load_dotenv()

APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "dev-only-change-this-secret")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ChangeMe123!")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./loan_agent.db")
SEED_DEMO_DATA = os.getenv("SEED_DEMO_DATA", "true").lower() == "true"
ALLOW_REAL_CALLS = os.getenv("ALLOW_REAL_CALLS", "false").lower() == "true"
