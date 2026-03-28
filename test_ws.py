import asyncio
import websockets
import json

async def main():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        msg = {"type": "MOVE", "x": 0.2, "y": 0.1}
        await websocket.send(json.dumps(msg))
        print("Sent:", msg)

        response = await websocket.recv()
        print("Received:", response)

asyncio.run(main())
