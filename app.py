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
# --- FIREBASE CONNECTION ---
if not firebase_admin._apps:
    try:
        # Read the JSON string from Streamlit Secrets
        key_dict = json.loads(st.secrets["firebase_key"])
        
        # Initialize Firebase with the secret key
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
    "Boutique Hotel (West Coast)": {"solar": 50.0, "bess": 100.0, "bess_pct": 80, "ev": 200.0, "ev_pct": 40},
    "Taxi Cooperative (10 EVs)": {"solar": 30.0, "bess": 200.0, "bess_pct": 90, "ev": 600.0, "ev_pct": 15}
}

selected_profile = st.sidebar.selectbox("📂 Load Client Profile", list(demo_profiles.keys()))

# Set default values based on selection
if selected_profile != "Select a Demo Profile...":
    default_solar = demo_profiles[selected_profile]["solar"]
    default_bess = demo_profiles[selected_profile]["bess"]
    default_bess_pct = demo_profiles[selected_profile]["bess_pct"]
    default_ev = demo_profiles[selected_profile]["ev"]
    default_ev_pct = demo_profiles[selected_profile]["ev_pct"]
else:
    default_solar = 5.0
    default_bess = 10.0
    default_bess_pct = 80
    default_ev = 60.0
    default_ev_pct = 30

st.sidebar.markdown("---")
st.sidebar.subheader("☀️ Solar Setup")
# Increased max_value to accommodate larger commercial profiles
pv_system_size_kw = st.sidebar.number_input("Solar Panel Size (kW)", min_value=1.0, max_value=500.0, value=default_solar, step=0.5)

st.sidebar.subheader("🏠 Home Battery (BESS)")
home_battery_capacity = st.sidebar.number_input("Battery Capacity (kWh)", min_value=1.0, max_value=500.0, value=default_bess, step=1.0)
home_battery_pct = st.sidebar.slider("Current Battery Level (%)", 0, 100, default_bess_pct)
home_battery_current = home_battery_capacity * (home_battery_pct / 100.0)

st.sidebar.subheader("⚡ Electric Vehicle (EV)")
ev_battery_capacity = st.sidebar.number_input("EV Battery Capacity (kWh)", min_value=10.0, max_value=1000.0, value=default_ev, step=5.0)
ev_battery_pct = st.sidebar.slider("Current EV Battery Level (%)", 0, 100, default_ev_pct)
ev_battery_current = ev_battery_capacity * (ev_battery_pct / 100.0)

# --- SOLAR DATA ---
@st.cache_data(ttl=3600)
def get_solar_data():
    lat, lon = 13.10, -59.53
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ["direct_radiation", "diffuse_radiation", "global_tilted_irradiance"],
        "timezone": "America/Barbados",
        "forecast_days": 1
    }
    response = requests.get(url, params=params)
    data = response.json()
    if 'hourly' not in data:
        df = pd.DataFrame({
            'Time': pd.date_range(start='2023-01-01', periods=24, freq='h'),
            'Direct_Rad': [0] * 24,
            'Diffuse_Rad': [0] * 24,
            'Global_Tilted': [0] * 24
        })
    else:
        df = pd.DataFrame({
            'Time': pd.to_datetime(data['hourly']['time']),
            'Direct_Rad': data['hourly']['direct_radiation'],
            'Diffuse_Rad': data['hourly']['diffuse_radiation'],
            'Global_Tilted': data['hourly']['global_tilted_irradiance']
        })
    return df

solar_df = get_solar_data()

# --- ALGORITHM ---
def calculate_optimal_schedule(df, pv_size):
    df['Solar_Production_kW'] = (df['Global_Tilted'] / 1000) * pv_size
    peak_hours = df.nlargest(3, 'Solar_Production_kW')['Time']
    start_time = peak_hours.min().strftime('%I:%M %p')
    end_time = peak_hours.max().strftime('%I:%M %p')
    # Returning the actual datetime objects to prevent Plotly crashes
    return df, start_time, end_time, peak_hours.min(), peak_hours.max()

processed_df, optimal_start, optimal_end, peak_start_dt, peak_end_dt = calculate_optimal_schedule(solar_df, pv_system_size_kw)

current_hour = datetime.now().hour
current_solar_output = processed_df.loc[processed_df['Time'].dt.hour == current_hour, 'Solar_Production_kW'].values[0] if not processed_df[processed_df['Time'].dt.hour == current_hour].empty else 0

# --- UI ---
st.title("☀️ Barbados Smart Energy Optimizer")
st.markdown("---")
st.markdown(f"<div style='text-align:center;'><h2>Optimal EV Charging: {optimal_start} to {optimal_end}</h2></div>", unsafe_allow_html=True)
st.markdown("---")

fig = go.Figure()
fig.add_trace(go.Scatter(x=processed_df['Time'], y=processed_df['Solar_Production_kW'], mode='lines', name='Solar (kW)', line=dict(color='orange', width=3)))

# Fixed: Using datetime objects for x0 and x1 to prevent Plotly rendering errors
fig.add_vrect(x0=peak_start_dt, x1=peak_end_dt, fillcolor="blue", opacity=0.2, annotation_text="EV Charging Window")
fig.update_layout(xaxis_title="Time", yaxis_title="kW", height=400)
st.plotly_chart(fig, use_container_width=True)

col1, col2, col3 = st.columns(3)
with col1: st.metric("Solar Output", f"{current_solar_output:.2f} kW")
with col2: st.metric("Home Battery", f"{home_battery_pct}%")
with col3: st.metric("EV Battery", f"{ev_battery_pct}%")

# --- SAVE BUTTON ---
st.markdown("---")
st.subheader("💾 Save to Cloud")
client_id_save = st.text_input("Client ID:", "demo_user", key="save_id")
if st.button("Save Data"):
    daily_summary = {
        "weather": "Sunny",
        "total_solar_kwh": round(processed_df['Solar_Production_kW'].sum(), 2),
        "total_ev_charging_kwh": round(ev_battery_capacity * 0.7, 2),
        "total_blpc_used_kwh": 0.0,
        "estimated_savings_bbd": round(processed_df['Solar_Production_kW'].sum() * 0.45, 2)
    }
    hourly_data = [{"hour": row['Time'].strftime('%H:00'), "solar_kw": round(row['Solar_Production_kW'], 2)} for idx, row in processed_df.iterrows()]
    save_daily_data_to_cloud(client_id_save, daily_summary, hourly_data)
    st.success("✅ Saved!")

# --- HISTORY ---
st.markdown("---")
st.subheader("📊 View History")
client_id_view = st.text_input("Client ID:", "demo_user", key="view_id")
if st.button("Fetch History"):
    history = load_history_from_cloud(client_id_view)
    if history:
        table_data = []
        for date, details in history.items():
            summary = details.get('summary', {})
            table_data.append({
                "Date": details.get('date', date),
                "Solar (kWh)": summary.get('total_solar_kwh', 0),
                "EV (kWh)": summary.get('total_ev_charging_kwh', 0),
                "Saved (BBD)": summary.get('estimated_savings_bbd', 0)
            })
        st.dataframe(pd.DataFrame(table_data), use_container_width=True)
    else:
        st.warning("No history found")
