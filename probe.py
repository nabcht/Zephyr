import asyncio
import json
import httpx
from backend.main import app
from backend.runtime_gateway import shutdown_runtime

async def main():
    stream_chunks = []
    
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        payload = {
            "session_id": "phase-three-local-fast-path",
            "message": "Reply with exactly OK. Do not call tools."
        }
        
        async with client.stream("POST", "/api/chat/stream", json=payload) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    content = line[len("data: "):]
                    if content == "[DONE]":
                        break
                    try:
                        data = json.loads(content)
                        if "choices" in data:
                            chunk = data["choices"][0].get("delta", {}).get("content", "")
                            if chunk:
                                stream_chunks.append(chunk)
                        elif "content" in data:
                            stream_chunks.append(data["content"])
                    except json.JSONDecodeError:
                        pass

        status_resp = await client.get("/api/system/status")
        status_data = status_resp.json()

    result = {
        "stream_chunks": stream_chunks,
        "inference_status": status_data.get("inference_status"),
        "inference_metrics": status_data.get("inference_metrics"),
        "provider_payload_metrics": status_data.get("provider_payload_metrics")
    }
    
    print(json.dumps(result))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        try:
            shutdown_runtime()
        except Exception:
            pass
