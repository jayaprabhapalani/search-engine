import os
from dotenv import load_dotenv
from celery import Celery

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")

celery_app = Celery(
    "hn_search",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["hn_search.tasks"],
)

celery_app.conf.beat_schedule = {
    "reindex-every-1-hours": {
        "task": "hn_search.tasks.reindex_stories",
        "schedule": 3600,
    },
    "enrich-every-30-minutes": {
        "task": "hn_search.tasks.enrich_stories",
        "schedule": 1800,
    },
    "embed-every-30-minutes": {
        "task": "hn_search.tasks.embed_chunks",
        "schedule": 1800,
        "options": {"queue": "embeddings"},
    },
}

celery_app.conf.task_routes = {
    "hn_search.tasks.embed_chunks": {"queue": "embeddings"},
}
