import os
from dotenv import load_dotenv
from celery import Celery
from celery.schedules import crontab

load_dotenv()

REDIS_URL=os.getenv("REDIS_URL")

#celery instance
celery_app=Celery(
    __name__,
    broker=REDIS_URL,
    backend=REDIS_URL
)

#beat schedule(for automatic reindexing)
celery_app.conf.beat_schedule={
    "reindex-every-1-hours":{
        "task":"hn_search.tasks.reindex_stories",
        "schedule":3600
    }
}