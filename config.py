"""Central configuration and constants (RepairSafe-style)."""
import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL = "llama-3.3-70b-versatile"

# SQLite audit log lives here (git-ignored via *.db).
DB_PATH = os.getenv("PROVENANCE_DB", "provenance.db")

# Attribution verdict vocabulary used across the system.
ATTR_AI = "likely_ai"
ATTR_HUMAN = "likely_human"
ATTR_UNCERTAIN = "uncertain"
VALID_ATTRIBUTIONS = {ATTR_AI, ATTR_HUMAN, ATTR_UNCERTAIN}
