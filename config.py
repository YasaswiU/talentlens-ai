import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    SECRET_KEY = os.environ.get("SKILLPALAVAR_SECRET_KEY", "dev-secret-key-change-in-production")

    DATABASE_PATH = os.path.join(BASE_DIR, "skillpalavar.db")

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    ALLOWED_EXTENSIONS = {"pdf"}
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB max resume size

    MODEL_PATH = os.path.join(BASE_DIR, "model.pkl")
    MODEL_METRICS_PATH = os.path.join(BASE_DIR, "model_metrics.json")
    FEATURE_IMPORTANCE_CHART = os.path.join(BASE_DIR, "static", "images", "feature_importance.png")

    # Ollama / LLM configuration
    OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:4b")
    OLLAMA_TIMEOUT_SECONDS = 20

    # Scoring weights (Section 16 of spec)
    WEIGHT_RESUME_MATCH = 0.40
    WEIGHT_QUIZ = 0.30
    WEIGHT_SKILLS = 0.20
    WEIGHT_EXPERIENCE = 0.10

    QUIZ_QUESTION_COUNT = 5
