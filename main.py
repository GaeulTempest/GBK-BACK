import uuid
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Inisialisasi aplikasi FastAPI
app = FastAPI()

# Menambahkan middleware CORS untuk mengizinkan koneksi dari semua sumber
# Ini penting untuk komunikasi antara Streamlit dan Railway
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoint untuk Health Check
# Ini untuk memastikan Railway tahu aplikasi kita berjalan
@app.get("/")
def read_root():
    return {"status": "Backend is healthy and running"}

# Endpoint untuk membuat room
# Ini adalah endpoint yang kita tes
@app.post("/create_room")
def create_room():
    """Membuat ID room yang unik."""
    room_id = str(uuid.uuid4())[:6]
    # Langsung kembalikan room_id dalam format JSON
    return {"room_id": room_id}

# Semua kode WebSocket dan ConnectionManager dihapus sementara untuk tes ini
