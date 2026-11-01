"""Local sink: stores only idempotency identifiers, never sends email."""

import sqlite3
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, Header
from pydantic import BaseModel, Field

app = FastAPI(title="Local notification sink")
path = Path("/data/receipts.sqlite")


class Mail(BaseModel):
    to: str = Field(max_length=320)
    subject: str = Field(max_length=200)
    text: str = Field(max_length=5000)


@app.post("/messages", status_code=202)
def accept(mail: Mail, idempotency_key: str = Header()):
    key = str(UUID(idempotency_key))
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE IF NOT EXISTS receipts (event_id TEXT PRIMARY KEY)")
        db.execute("INSERT OR IGNORE INTO receipts VALUES (?)", (key,))
    return {"accepted": True}


@app.get("/health")
def health():
    return {"status": "ok"}
