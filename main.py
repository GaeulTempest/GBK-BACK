import asyncio
import json
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import Dict, List, Tuple

# Inisialisasi aplikasi FastAPI
app = FastAPI()

# =====================================================================
# TAMBAHAN: Endpoint untuk Health Check dari Railway
# =====================================================================
@app.get("/")
async def root():
    """Endpoint ini merespons health check dari Railway."""
    return {"message": "Backend Gunting Batu Kertas is running"}
# =====================================================================

# Objek untuk mengelola koneksi WebSocket yang aktif
class ConnectionManager:
    def __init__(self):
        # Menyimpan koneksi aktif per room_id
        # Format: { "room_id": [websocket1, websocket2] }
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        # Menerima koneksi baru
        await websocket.accept()
        # Jika room belum ada, buat list baru
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        # Tambahkan koneksi ke room
        self.active_connections[room_id].append(websocket)

    def disconnect(self, websocket: WebSocket, room_id: str):
        # Menghapus koneksi saat client terputus
        if room_id in self.active_connections:
            self.active_connections[room_id].remove(websocket)
            # Jika room kosong, hapus room
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

    async def broadcast(self, message: str, room_id: str):
        # Mengirim pesan ke semua client di dalam satu room
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                await connection.send_text(message)

# Inisialisasi manager koneksi
manager = ConnectionManager()

# Variabel untuk menyimpan state permainan (gerakan pemain, skor, dll.)
game_state: Dict[str, Dict] = {}

# Fungsi untuk menentukan pemenang
def determine_winner(move1: str, move2: str) -> str:
    """Menentukan pemenang berdasarkan aturan Gunting Batu Kertas."""
    if move1 == move2:
        return "draw"
    rules = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
    if rules.get(move1) == move2:
        return "player1"
    return "player2"

# Endpoint untuk membuat room baru
@app.post("/create_room")
async def create_room():
    """Membuat ID room yang unik dan menginisialisasi state permainan."""
    room_id = str(uuid.uuid4())[:6]  # Ambil 6 karakter pertama dari UUID
    game_state[room_id] = {"moves": {}, "scores": {"player1": 0, "player2": 0}}
    return {"room_id": room_id}

# Endpoint untuk mengecek ketersediaan room
@app.get("/check_room/{room_id}")
async def check_room(room_id: str):
    """Mengecek apakah room ada dan belum penuh."""
    if room_id in manager.active_connections:
        if len(manager.active_connections[room_id]) >= 2:
            return {"status": "full"}
        return {"status": "available"}
    return {"status": "not_found"}

# Endpoint WebSocket utama untuk gameplay
@app.websocket("/ws/{room_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_id: str):
    await manager.connect(websocket, room_id)
    
    # Kirim pesan bahwa pemain telah bergabung
    join_message = json.dumps({"type": "player_join", "player_id": player_id})
    await manager.broadcast(join_message, room_id)

    try:
        while True:
            # Menunggu data dari client (frontend)
            data = await websocket.receive_text()
            message = json.loads(data)

            # Jika pesan adalah gerakan pemain
            if message.get("type") == "move":
                current_moves = game_state.get(room_id, {}).get("moves", {})
                current_moves[player_id] = message["move"]
                
                # Jika kedua pemain sudah membuat gerakan
                if len(current_moves) == 2:
                    # Ambil ID dan gerakan kedua pemain
                    p1_id, p1_move = list(current_moves.items())[0]
                    p2_id, p2_move = list(current_moves.items())[1]
                    
                    # Tentukan pemenang
                    winner_player = determine_winner(p1_move, p2_move)
                    
                    winner_id = None
                    if winner_player == "player1":
                        winner_id = p1_id
                    elif winner_player == "player2":
                        winner_id = p2_id

                    # Buat pesan hasil
                    result_message = json.dumps({
                        "type": "result",
                        "winner": winner_id,
                        "moves": current_moves
                    })
                    
                    # Kirim hasil ke semua pemain di room
                    await manager.broadcast(result_message, room_id)
                    
                    # Reset gerakan untuk ronde selanjutnya
                    game_state[room_id]["moves"] = {}

    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
        # Kirim pesan bahwa pemain telah keluar
        leave_message = json.dumps({"type": "player_leave", "player_id": player_id})
        await manager.broadcast(leave_message, room_id)
