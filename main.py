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
        # socket_map: WebSocket -> client_id
        self.socket_map: Dict[WebSocket, str] = {}

    async def connect(self, room_id: str, client_id: str, websocket: WebSocket):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)
        self.socket_map[websocket] = client_id

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_connections:
            if websocket in self.active_connections[room_id]:
                self.active_connections[room_id].remove(websocket)
        if websocket in self.socket_map:
            del self.socket_map[websocket]

    def get_room(self, room_id: str):
        return get_or_create_room(room_id)

    async def send_personal_message(self, websocket: WebSocket, message: dict):
        try:
             json_msg = json.dumps(message, default=str)
             await websocket.send_text(json_msg)
        except Exception:
            pass

    async def broadcast_state(self, room_id: str):
        if room_id in self.active_connections:
            room = get_or_create_room(room_id)
            
            # Broadcast loop with per-player filtering
            active = self.active_connections[room_id][:]
            for connection in active:
                client_id = self.socket_map.get(connection)
                if not client_id:
                    continue
                
                # Create sanitized view for this player
                view_data = room.get_view(client_id)
                
                message = {
                    "type": "STATE_UPDATE",
                    "data": view_data
                }
                
                try:
                    await connection.send_text(json.dumps(message, default=str))
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
            
            # Special Handling for PEEK which is personal
            if msg_type == "WEREWOLF_PEEK":
                target = payload.get("target")
                result = room.handle_seer_peek(client_id, target)
                await manager.send_personal_message(websocket, {
                    "type": "WEREWOLF_PEEK_RESULT",
                    "data": {"result": result, "target": target}
                })
                continue

            if engine.process_message(room, client_id, msg_type, payload):
                await manager.broadcast_state(room_id)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
        await manager.broadcast_state(room_id)
