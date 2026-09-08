import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, db
import os
import json
import glob

# --- FIREBASE CONNECTION ---
if not firebase_admin._apps:
    try:
        # Build the credentials dict from individual TOML fields (Bulletproof method)
        key_dict = {
            "type": st.secrets["firebase"]["type"],
            "project_id": st.secrets["firebase"]["project_id"],
            "private_key_id": st.secrets["firebase"]["private_key_id"],
            "private_key": st.secrets["firebase"]["private_key"].replace("\\n", "\n"),
            "client_email": st.secrets["firebase"]["client_email"],
            "client_id": st.secrets["firebase"]["client_id"],
            "auth_uri": st.secrets["firebase"]["auth_uri"],
            "token_uri": st.secrets["firebase"]["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["firebase"]["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["firebase"]["client_x509_cert_url"]
        }
        
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://barbados-solar-sept226-default-rtdb.firebaseio.com/'
        })
    except Exception as e:
        st.error(f"Error connecting to database: {e}")
        st.stop()

# --- SAVE FUNCTION ---
def save_daily_data_to_cloud(client_id, daily_summary, hourly_data):
    today_date = datetime.today().strftime("%Y-%m-%d")
    exact_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ref = db.reference(f"users/{client_id}/history/{today_date}")
    data_to_save = {
        "timestamp": exact_time,
        "date": today_date,
        "summary": daily_summary,
        "hourly_details": hourly_data
    }
    ref.set(data_to_save)

# --- LOAD FUNCTION ---
def load_history_from_cloud(client_id):
    ref = db.reference(f"users/{client_id}/history")
    history = ref.get()
    return history

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Barbados Energy Optimizer", layout="wide", page_icon="☀️")

# --- SIDEBAR ---
st.sidebar.title("⚙️ System Configuration")
st.sidebar.markdown("---")

# --- NEW: DEMO PROFILES DROPDOWN ---
demo_profiles = {
    "Select a Demo Profile...": {"solar": 5.0, "bess": 10.0, "bess_pct": 80, "ev": 60.0, "ev_pct": 30},
    "Residential Home": {"solar": 10.0, "bess": 15.0, "bess_pct": 50, "ev": 75.0, "ev_pct": 20},
    "Boutique Hotel (West Coast)": {"solar": 50.0, "bess
