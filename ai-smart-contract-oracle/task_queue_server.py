from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

app = FastAPI()

class Task(BaseModel):
    contract_address: str
    source_code: str | None = None
    bytecode: str | None = None

TASKS = []

@app.get("/pending")
def pending():
    return TASKS

@app.post("/enqueue")
def enqueue(task: Task):
    TASKS.append(task.dict())
    return {"status": "queued"}

@app.post("/mark-complete")
def mark_complete(data: dict):
    addr = data.get("contract_address")
    TASKS[:] = [t for t in TASKS if t["contract_address"] != addr]
    return {"status": "cleared"}

if __name__ == "__main__":
    uvicorn.run("task_queue_server:app", host="0.0.0.0", port=9000)
