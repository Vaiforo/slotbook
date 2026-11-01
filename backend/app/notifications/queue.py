from celery import Celery
from kombu import Queue

from app.core.config import Settings

celery = Celery("slotbook", broker=Settings().broker_url)
celery.conf.update(
    task_queues=[Queue("notifications", durable=True)],
    task_default_queue="notifications",
    task_default_delivery_mode=2,
    task_serializer="json",
    accept_content=["json"],
    task_ignore_result=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_transport_options={"confirm_publish": True},
    broker_connection_timeout=3,
    task_publish_retry=False,
    broker_connection_retry_on_startup=True,
)
celery.conf.imports = ("app.notifications.tasks",)
