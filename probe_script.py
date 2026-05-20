import asyncio
import json
import httpx
from backend.main import app

async def run_probe():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. POST /api/chat/stream
        chat_payload = {
            "session_id": "phase-three-lightweight-prompt-trim",
            "message": "Reply with exactly OK. Do not call tools."
        }
        async with client.stream("POST", "/api/chat/stream", json=chat_payload) as response:
            async for line in response.aiter_lines():
                pass
        
        # 2. GET /api/system/status
        status_response = await client.get("/api/system/status")
        status_data = status_response.json()
        
        # 3. Extract metrics
        result = {
            "provider_payload_metrics": status_data.get("provider_payload_metrics"),
            "inference_metrics": status_data.get("inference_metrics")
        }
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(run_probe())
