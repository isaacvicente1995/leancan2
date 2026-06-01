import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="LeanCan", page_icon="🥫", layout="wide")

st.title("🥫 LeanCan Scheduler")

# Configuración directa (después la moveremos a secrets)
SUPABASE_URL = "https://nubxhtlertuwmevxzuyd.supabase.co/rest/v1"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im51YnhodGxlcnR1d21ldnh6dXlkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODAzMTI4ODYsImV4cCI6MjA5NTg4ODg4Nn0.sxXfypXZHyqFnXL1xeXdvXw925C6v-dg9Kg--7KNLWs"

# Probar conexión
try:
    response = requests.get(
        f"{SUPABASE_URL}/maquinas",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    )
    if response.status_code == 200:
        st.success("✅ Conectado a Supabase")
        st.write("Datos de máquinas:", response.json())
    else:
        st.error(f"Error: {response.status_code} - {response.text}")
except Exception as e:
    st.error(f"Error de conexión: {e}")
