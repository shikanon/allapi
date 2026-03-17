from __future__ import annotations

from fastapi import FastAPI, Request


app = FastAPI(title="mock-upstream")


@app.post("/api/v3/contents/generations/tasks")
async def create_task(request: Request):
    _ = await request.json()
    return {"id": "cgt-mock-001"}


@app.get("/api/v3/contents/generations/tasks/{task_id}")
def get_task(task_id: str):
    return {
        "id": task_id,
        "status": "succeeded",
        "usage": {"completion_tokens": 108900, "total_tokens": 108900},
        "content": {"video_url": "https://example.com/video.mp4"},
    }


@app.post("/api/v3/contents/generations/tasks/{task_id}/cancel")
def cancel_task(task_id: str):
    return {"id": task_id, "status": "cancelled", "cancelled": True}

