import json
import asyncio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.engine import MultiAgentEngine

app = FastAPI(
    title="Autonomous Multi-Agent Sandbox API",
    description="Backend orchestration service for Coder & Critic autonomous workflows",
    version="1.0.0"
)

# Enable CORS for the web UI frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TaskRequest(BaseModel):
    goal: str
    max_iterations: int = 4

@app.get("/")
def health_check():
    return {"status": "online", "service": "multi-agent-engine"}

@app.post("/api/run")
async def run_task(payload: TaskRequest):
    """Synchronous execution endpoint returning final result."""
    engine = MultiAgentEngine(max_iterations=payload.max_iterations)
    events = list(engine.run_stream(payload.goal))
    return {"events": events}

@app.get("/api/stream")
async def stream_task(goal: str, max_iterations: int = 4):
    """
    Server-Sent Events (SSE) streaming endpoint.
    Streams each step of the agent reasoning loop to the browser in real time.
    """
    engine = MultiAgentEngine(max_iterations=max_iterations)

    async def event_generator():
        for event in engine.run_stream(goal):
            data = json.dumps(event)
            yield f"data: {data}\n\n"
            # Brief micro-yield to keep async event loop responsive
            await asyncio.sleep(0.05)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
