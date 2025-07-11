import asyncio
import json
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List

# 1. Inisialisasi Aplikasi FastAPI
app = FastAPI()

# 2. Konfigurasi CORS (Cross-Origin Resource Sharing)
# Ini sangat penting agar frontend Anda (dari domain Streamlit)
# diizinkan untuk berkomunikasi dengan backend ini (di domain Railway).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Mengizinkan koneksi dari semua sumber/domain
    allow_credentials=True,
    allow_methods=["*"],  # Mengizinkan semua metode HTTP (GET, POST, dll.)
    allow_headers=["*"],  # Mengizinkan semua header HTTP
)

# 3. Manajer Koneksi WebSocket
# Kelas ini bertugas untuk mengelola siapa saja yang terhubung ke room mana.
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_connections and websocket in self.active_connections[room_id]:
            self.active_connections[room_id].remove(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

    async def broadcast(self, message: str, room_id: str):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                await connection.send_text(message)

manager = ConnectionManager()

# 4. State Permainan
# Variabel global untuk menyimpan data permainan yang sedang berlangsung.
game_state: Dict[str, Dict] = {}

# 5. Logika Inti Permainan
def determine_winner(move1: str, move2: str) -> str:
    """Menentukan pemenang berdasarkan aturan Gunting Batu Kertas."""
    if move1 == move2:
        return "draw"
    rules = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
    if rules.get(move1) == move2:
        return "player1"
    return "player2"

# 6. Endpoints HTTP
@app.get("/")
async def root():
    """Endpoint untuk Health Check dari Railway."""
    return {"message": "Backend Gunting Batu Kertas is running"}

@app.post("/create_room")
async def create_room():
    """Membuat ID room yang unik dan menginisialisasi state permainan."""
    room_id = str(uuid.uuid4())[:6]
    game_state[room_id] = {"moves": {}, "players": []}
    return {"room_id": room_id}

# 7. Endpoint WebSocket Utama untuk Gameplay
@app.websocket("/ws/{room_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_id: str):
    await manager.connect(websocket, room_id)
    
    # Daftarkan pemain ke state
    if room_id in game_state and player_id not in game_state[room_id]["players"]:
        game_state[room_id]["players"].append(player_id)
    
    # Kirim pesan bahwa pemain telah bergabung
    join_message = json.dumps({
        "type": "player_update", 
        "player_count": len(game_state.get(room_id, {}).get("players", [])),
        "player_id": player_id
    })
    await manager.broadcast(join_message, room_id)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "move":
                current_moves = game_state.get(room_id, {}).get("moves", {})
                current_moves[player_id] = message["move"]
                
                # Cek jika kedua pemain sudah membuat gerakan
                if len(current_moves) == 2:
                    p1_id, p1_move = list(current_moves.items())[0]
                    p2_id, p2_move = list(current_moves.items())[1]
                    
                    # Tentukan pemenang berdasarkan siapa yang mengirim gerakan pertama
                    winner_player = determine_winner(p1_move, p2_move)
                    winner_id = None
                    if winner_player == "player1": winner_id = p1_id
                    elif winner_player == "player2": winner_id = p2_id

                    result_message = json.dumps({
                        "type": "result",
                        "winner": winner_id,
                        "moves": current_moves
                    })
                    
                    await manager.broadcast(result_message, room_id)
                    game_state[room_id]["moves"] = {}

    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
        # Hapus pemain dari state saat disconnect
        if room_id in game_state and player_id in game_state[room_id]["players"]:
            game_state[room_id]["players"].remove(player_id)
        
        leave_message = json.dumps({
            "type": "player_update",
            "player_count": len(game_state.get(room_id, {}).get("players", [])),
            "player_id": player_id
        })
        await manager.broadcast(leave_message, room_id)
