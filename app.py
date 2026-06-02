from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
import os

app = FastAPI()

# Configurar CORS para permitir conexión desde el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, poner tu dominio de Vercel
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de Supabase
SUPABASE_URL = "https://nubxhtlertuwmevxzuyd.supabase.co/rest/v1"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

@app.get("/api/maquinas")
def get_maquinas():
    response = requests.get(
        f"{SUPABASE_URL}/maquinas",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    )
    return response.json()

@app.get("/api/pedidos")
def get_pedidos():
    response = requests.get(
        f"{SUPABASE_URL}/pedidos",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    )
    return response.json()

@app.get("/api/health")
def health():
    return {"status": "ok"}
