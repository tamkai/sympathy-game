from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from typing import List, Dict
import json
import uuid

from models import Room, Player, Phase, get_or_create_room, rooms, GameMode, WordWolfState

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

from game_engine import GameEngine
engine = GameEngine()


def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

@app.on_event("startup")
async def startup_event():
    ip = get_local_ip()
    print(f"\n{'='*40}")
    print(f"🚀 Game Server Running!")
    print(f"🏠 Local: http://127.0.0.1:8000/host/<RoomID>")
    print(f"🌐 Network (For Smartphones): http://{ip}:8000/host/<RoomID>")
    print(f"{'='*40}\n")

class ConnectionManager:
    def __init__(self):
        # active_connections: room_id -> list of WebSockets
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, room_id: str, client_id: str, websocket: WebSocket):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_connections:
            if websocket in self.active_connections[room_id]:
                self.active_connections[room_id].remove(websocket)

    def get_room(self, room_id: str):
        return get_or_create_room(room_id)

    async def broadcast_state(self, room_id: str):
        if room_id in self.active_connections:
            room = get_or_create_room(room_id)
            # Serialize room state using Pydantic's model_dump_json()
            message = {
                "type": "STATE_UPDATE",
                "data": room.model_dump()
            }
            json_msg = json.dumps(message, default=str) # default=str to handle UUIDs/Enums if needed
            
            # Simple broadcast loop
            # In a real app, handle broken pipes gracefully
            active = self.active_connections[room_id][:]
            for connection in active:
                try:
                    await connection.send_text(json_msg)
                except Exception:
                    # Clean up broken connections?
                    # self.disconnect(connection, room_id)
                    pass

manager = ConnectionManager()

@app.get("/", response_class=HTMLResponse)
async def get_landing(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/host/{room_id}", response_class=HTMLResponse)
async def get_host(request: Request, room_id: str):
    network_ip = get_local_ip()
    return templates.TemplateResponse("host.html", {
        "request": request,
        "room_id": room_id,
        "network_ip": network_ip
    })

@app.get("/play/{room_id}", response_class=HTMLResponse)
async def get_player(request: Request, room_id: str):
    return templates.TemplateResponse("player.html", {"request": request, "room_id": room_id})





@app.websocket("/ws/{room_id}/{client_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, client_id: str):
    await manager.connect(room_id, client_id, websocket)
    room = manager.get_room(room_id)
    
    # Broadcast initial state to the new connector
    await manager.broadcast_state(room_id)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            msg_type = message.get("type")
            payload = message.get("data", {})

            # --- Message Handling Logic ---
            if engine.process_message(room, client_id, msg_type, payload):
                await manager.broadcast_state(room_id)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
        # await manager.broadcast(f"Client #{client_id} left the chat")

    except WebSocketDisconnect:
        manager.disconnect(room_id, client_id)
        # Optional: Remove player from game if disconnected? usually keep for reconnection.
        # But if desired: room.players.pop(client_id, None)
        await manager.broadcast_state(room_id)
