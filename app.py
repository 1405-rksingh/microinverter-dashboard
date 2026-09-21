"""
Microinverter Performance Dashboard
India Comparison Study - Atmoce vs. Enphase Data Analysis

Deployed on Streamlit Cloud
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Page config
st.set_page_config(
    page_title="Microinverter Performance Dashboard",
    page_icon="⚡",
    layout="wide"
)

# Enphase serial numbers
ENPHASE_LEFT = '482309046901'
ENPHASE_RIGHT = '482309046789'

# Colors - Green shades for Atmoce, Orange/Red shades for Enphase
colors = {
    'atmoce': '#27ae60',           # Green (main)
    'atmoce_pv1': '#2ecc71',       # Light green
    'atmoce_pv2': '#1e8449',       # Dark green
    'enphase': '#e67e22',          # Orange (main)
    'enphase_left': '#e74c3c',     # Red
    'enphase_right': '#f39c12',    # Yellow-orange
}

def load_atmoce_data():
    """Load and clean Atmoce Excel files"""
    all_data = []
    data_dir = 'data/atmoce'
    
    for file in os.listdir(data_dir):
        if file.endswith('.xlsx') and file.startswith('MicroInverter'):
            filepath = os.path.join(data_dir, file)
            xl = pd.ExcelFile(filepath)
            for sheet in xl.sheet_names:
                df = pd.read_excel(xl, sheet_name=sheet, header=1)
                df.columns = ['Serial Number', 'Time', 'Generated Power (W)', 'Grid Voltage (V)', 
                             'Frequency (Hz)', 'Daily Produced (kWh)', 'PV1 Power (W)', 
                             'PV1 Voltage (V)', 'PV2 Power (W)', 'PV2 Voltage (V)']
                all_data.append(df)
    
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        combined_df['Time'] = pd.to_datetime(combined_df['Time'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
        combined_df = combined_df.drop_duplicates(subset=['Time'], keep='last')
        combined_df = combined_df.sort_values('Time').dropna(subset=['Time'])
        combined_df['Date'] = combined_df['Time'].dt.date
        combined_df['PV1 Current (A)'] = (combined_df['PV1 Power (W)'] / combined_df['PV1 Voltage (V)']).replace([np.inf, -np.inf], 0).fillna(0)
        combined_df['PV2 Current (A)'] = (combined_df['PV2 Power (W)'] / combined_df['PV2 Voltage (V)']).replace([np.inf, -np.inf], 0).fillna(0)
        return combined_df
    return pd.DataFrame()

def load_enphase_data():
    """Load and clean Enphase CSV files"""
    all_data = []
    data_dir = 'data/enphase'
    
    for file in os.listdir(data_dir):
        if file.endswith('.csv'):
            filepath = os.path.join(data_dir, file)
            df = pd.read_csv(filepath)
            serial = file.replace('_readings.csv', '')
            df['Serial Number'] = serial
            all_data.append(df)
    
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        combined_df['Time'] = pd.to_datetime(combined_df['date'], errors='coerce')
        combined_df['Time'] = combined_df['Time'].dt.tz_localize(None)
        combined_df = combined_df.sort_values('Time').dropna(subset=['Time'])
        combined_df['Date'] = combined_df['Time'].dt.date
        combined_df = combined_df.rename(columns={
            'ac_voltage': 'Grid Voltage (V)', 'ac_frequency': 'Frequency (Hz)',
            'dc_voltage': 'DC Voltage (V)', 'dc_current': 'DC Current (A)',
            'energy_produced': 'Energy Produced (J)', 'pcu_ac_current': 'PCU AC Current (mA)'
        })
        combined_df['DC Power (W)'] = combined_df['DC Voltage (V)'] * combined_df['DC Current (A)']
        combined_df['AC Power (W)'] = (combined_df['PCU AC Current (mA)'] / 1000) * combined_df['Grid Voltage (V)']
        return combined_df
    return pd.DataFrame()

def round_to_15min(df, value_columns, serial_col='Serial Number'):
    """Round Enphase timestamps to nearest 15-minute intervals (no interpolation)"""
    df = df.copy()
    # Round time to nearest 15 minutes
    df['Time_Rounded'] = df['Time'].dt.round('15min')
    
    # Group by rounded time and serial, take mean of values
    grouped = df.groupby(['Time_Rounded', serial_col]).agg({
        **{col: 'mean' for col in value_columns if col in df.columns},
        'Energy Produced (J)': 'sum'  # Sum energy, not average
    }).reset_index()
    grouped = grouped.rename(columns={'Time_Rounded': 'Time'})
    
    return grouped

# Load data
atmoce_df = load_atmoce_data()
enphase_df_raw = load_enphase_data()

value_cols = ['DC Voltage (V)', 'DC Current (A)', 'DC Power (W)', 'AC Power (W)', 'Grid Voltage (V)', 'Frequency (Hz)']
enphase_df = round_to_15min(enphase_df_raw, value_cols)
enphase_df['Date'] = enphase_df['Time'].dt.date

common_dates = sorted(set(atmoce_df['Date'].unique()) & set(enphase_df['Date'].unique()))

# Aggregate Enphase data by time (sum both inverters) - NO interpolation
enphase_agg = enphase_df.groupby('Time').agg({
    'AC Power (W)': 'sum', 'DC Power (W)': 'sum', 'Grid Voltage (V)': 'mean',
    'Frequency (Hz)': 'mean', 'DC Voltage (V)': 'mean', 'DC Current (A)': 'sum'
}).reset_index()
enphase_agg['Date'] = enphase_agg['Time'].dt.date

# Header
st.title("⚡ Microinverter Performance Dashboard")
st.markdown("### India Comparison Study - Atmoce vs. Enphase Data Analysis")

st.markdown(f"""
**Devices:** 
<span style='color:{colors["atmoce"]}; font-weight:bold'>Atmoce ES26422038F</span> | 
<span style='color:{colors["enphase_left"]}; font-weight:bold'>IQ8P {ENPHASE_LEFT}</span> | 
<span style='color:{colors["enphase_right"]}; font-weight:bold'>IQ8P {ENPHASE_RIGHT}</span>
""", unsafe_allow_html=True)

st.markdown(f"**Data Range:** Atmoce ({atmoce_df['Time'].min().strftime('%d/%m/%Y')} - {atmoce_df['Time'].max().strftime('%d/%m/%Y')}) | Enphase ({enphase_df['Time'].min().strftime('%d/%m/%Y')} - {enphase_df['Time'].max().strftime('%d/%m/%Y')})")

st.divider()

# Date Range Selector
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start Date", value=min(common_dates), min_value=min(common_dates), max_value=max(common_dates))
with col2:
    end_date = st.date_input("End Date", value=max(common_dates), min_value=min(common_dates), max_value=max(common_dates))

# Filter data
atmoce_filtered = atmoce_df[(atmoce_df['Date'] >= start_date) & (atmoce_df['Date'] <= end_date)]
enphase_filtered = enphase_df[(enphase_df['Date'] >= start_date) & (enphase_df['Date'] <= end_date)]
enphase_agg_filtered = enphase_agg[(enphase_agg['Date'] >= start_date) & (enphase_agg['Date'] <= end_date)]
enphase_raw_filtered = enphase_df_raw[(enphase_df_raw['Date'] >= start_date) & (enphase_df_raw['Date'] <= end_date)]

enphase_left = enphase_filtered[enphase_filtered['Serial Number'] == ENPHASE_LEFT]
enphase_right = enphase_filtered[enphase_filtered['Serial Number'] == ENPHASE_RIGHT]

# Calculate metrics
atmoce_energy = atmoce_filtered.groupby('Date')['Daily Produced (kWh)'].max().sum() if len(atmoce_filtered) > 0 else 0
enphase_energy = enphase_raw_filtered['Energy Produced (J)'].sum() / 3600000 if len(enphase_raw_filtered) > 0 else 0
atmoce_peak = atmoce_filtered['Generated Power (W)'].max() if len(atmoce_filtered) > 0 else 0
enphase_left_peak = enphase_left['AC Power (W)'].max() if len(enphase_left) > 0 else 0
enphase_right_peak = enphase_right['AC Power (W)'].max() if len(enphase_right) > 0 else 0
atmoce_avg_voltage = atmoce_filtered['Grid Voltage (V)'].mean() if len(atmoce_filtered) > 0 else 0
enphase_avg_voltage = enphase_filtered['Grid Voltage (V)'].mean() if len(enphase_filtered) > 0 else 0
atmoce_avg_freq = atmoce_filtered['Frequency (Hz)'].mean() if len(atmoce_filtered) > 0 else 0
enphase_avg_freq = enphase_filtered['Frequency (Hz)'].mean() if len(enphase_filtered) > 0 else 0

# Performance Summary Cards
st.subheader("Performance Summary")
col1, col2 = st.columns(2)

with col1:
    st.markdown(f"""
    <div style='background-color:white; padding:20px; border-radius:10px; border-top:4px solid {colors["atmoce"]}; box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>
        <h3 style='color:{colors["atmoce"]}; margin-bottom:5px;'>ATMOCE</h3>
        <p style='color:#666; font-size:12px;'>ES26422038F</p>
        <hr>
        <p><b>Total Energy:</b> <span style='color:{colors["atmoce"]}; font-size:20px;'>{atmoce_energy:.2f} kWh</span></p>
        <p><b>Peak Power:</b> {atmoce_peak:.0f} W</p>
        <p><b>Avg Voltage:</b> {atmoce_avg_voltage:.1f} V</p>
        <p><b>Avg Frequency:</b> {atmoce_avg_freq:.2f} Hz</p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div style='background-color:white; padding:20px; border-radius:10px; border-top:4px solid {colors["enphase"]}; box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>
        <h3 style='color:{colors["enphase"]}; margin-bottom:5px;'>ENPHASE</h3>
        <p style='color:#666; font-size:12px;'>IQ8P {ENPHASE_LEFT[-4:]} + IQ8P {ENPHASE_RIGHT[-4:]}</p>
        <hr>
        <p><b>Total Energy:</b> <span style='color:{colors["enphase"]}; font-size:20px;'>{enphase_energy:.2f} kWh</span></p>
        <p><b>Peak Power ({ENPHASE_LEFT[-4:]}):</b> <span style='color:{colors["enphase_left"]};'>{enphase_left_peak:.0f} W</span></p>
        <p><b>Peak Power ({ENPHASE_RIGHT[-4:]}):</b> <span style='color:{colors["enphase_right"]};'>{enphase_right_peak:.0f} W</span></p>
        <p><b>Avg Voltage:</b> {enphase_avg_voltage:.1f} V</p>
        <p><b>Avg Frequency:</b> {enphase_avg_freq:.2f} Hz</p>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# Daily Energy Comparison
st.subheader("Daily Energy Comparison")
atmoce_daily = atmoce_filtered.groupby('Date')['Daily Produced (kWh)'].max().reset_index()
enphase_daily = enphase_raw_filtered.groupby('Date')['Energy Produced (J)'].sum().reset_index()
enphase_daily['Energy (kWh)'] = enphase_daily['Energy Produced (J)'] / 3600000

daily_fig = go.Figure()
daily_fig.add_trace(go.Bar(x=[str(d) for d in atmoce_daily['Date']], y=atmoce_daily['Daily Produced (kWh)'],
    name='Atmoce', marker_color=colors['atmoce'], text=[f"{v:.2f}" for v in atmoce_daily['Daily Produced (kWh)']], textposition='outside'))
daily_fig.add_trace(go.Bar(x=[str(d) for d in enphase_daily['Date']], y=enphase_daily['Energy (kWh)'],
    name='Enphase', marker_color=colors['enphase'], text=[f"{v:.2f}" for v in enphase_daily['Energy (kWh)']], textposition='outside'))
daily_fig.update_layout(xaxis_title='Date', yaxis_title='Energy (kWh)', barmode='group', template='plotly_white', height=400)
st.plotly_chart(daily_fig, use_container_width=True)

st.info("📌 **Shadow Experiment:** We conducted a shadow experiment from September 18-21, 2026, where we covered one PV module from each company to analyze their performance under partial shading conditions.")

# Power Generation Over Time
st.subheader("Power Generation Over Time (AC Power)")
st.caption("Atmoce: Generated Power | Enphase: (PCU AC Current × AC Voltage) Combined")

power_fig = go.Figure()
power_fig.add_trace(go.Scatter(x=atmoce_filtered['Time'], y=atmoce_filtered['Generated Power (W)'],
    mode='lines', name='Atmoce', line=dict(color=colors['atmoce'], width=2), 
    fill='tozeroy', fillcolor='rgba(39, 174, 96, 0.2)',
    connectgaps=False))  # Don't connect gaps
power_fig.add_trace(go.Scatter(x=enphase_agg_filtered['Time'], y=enphase_agg_filtered['AC Power (W)'],
    mode='lines+markers', name='Enphase (Combined)', line=dict(color=colors['enphase'], width=2),
    marker=dict(size=5),
    connectgaps=False))  # Don't connect gaps - shows actual data points only
power_fig.update_layout(xaxis_title='Time', yaxis_title='Power (W)', template='plotly_white', height=400, hovermode='x unified')
st.plotly_chart(power_fig, use_container_width=True)

# DC Power Comparison
st.subheader("DC Power Comparison (4 PV Panels)")
st.caption("Atmoce PV1, Atmoce PV2, PVleft (IQ8P 6901), PVright (IQ8P 6789)")

dc_power_fig = go.Figure()
dc_power_fig.add_trace(go.Scatter(x=atmoce_filtered['Time'], y=atmoce_filtered['PV1 Power (W)'],
    mode='lines', name='Atmoce PV1', line=dict(color=colors['atmoce_pv1'], width=2), connectgaps=False))
dc_power_fig.add_trace(go.Scatter(x=atmoce_filtered['Time'], y=atmoce_filtered['PV2 Power (W)'],
    mode='lines', name='Atmoce PV2', line=dict(color=colors['atmoce_pv2'], width=2), connectgaps=False))
dc_power_fig.add_trace(go.Scatter(x=enphase_left['Time'], y=enphase_left['DC Power (W)'],
    mode='lines+markers', name='PVleft (6901)', line=dict(color=colors['enphase_left'], width=2), 
    marker=dict(size=4), connectgaps=False))
dc_power_fig.add_trace(go.Scatter(x=enphase_right['Time'], y=enphase_right['DC Power (W)'],
    mode='lines+markers', name='PVright (6789)', line=dict(color=colors['enphase_right'], width=2),
    marker=dict(size=4), connectgaps=False))
dc_power_fig.update_layout(xaxis_title='Time', yaxis_title='DC Power (W)', template='plotly_white', height=400, hovermode='x unified')
st.plotly_chart(dc_power_fig, use_container_width=True)

# DC Voltage and Current side by side
col1, col2 = st.columns(2)

with col1:
    st.subheader("DC Voltage Comparison")
    dc_voltage_fig = go.Figure()
    dc_voltage_fig.add_trace(go.Scatter(x=atmoce_filtered['Time'], y=atmoce_filtered['PV1 Voltage (V)'],
        mode='lines', name='Atmoce PV1', line=dict(color=colors['atmoce_pv1'], width=2), connectgaps=False))
    dc_voltage_fig.add_trace(go.Scatter(x=atmoce_filtered['Time'], y=atmoce_filtered['PV2 Voltage (V)'],
        mode='lines', name='Atmoce PV2', line=dict(color=colors['atmoce_pv2'], width=2), connectgaps=False))
    dc_voltage_fig.add_trace(go.Scatter(x=enphase_left['Time'], y=enphase_left['DC Voltage (V)'],
        mode='lines+markers', name='PVleft (6901)', line=dict(color=colors['enphase_left'], width=2),
        marker=dict(size=4), connectgaps=False))
    dc_voltage_fig.add_trace(go.Scatter(x=enphase_right['Time'], y=enphase_right['DC Voltage (V)'],
        mode='lines+markers', name='PVright (6789)', line=dict(color=colors['enphase_right'], width=2),
        marker=dict(size=4), connectgaps=False))
    dc_voltage_fig.update_layout(xaxis_title='Time', yaxis_title='Voltage (V)', template='plotly_white', height=350, hovermode='x unified')
    st.plotly_chart(dc_voltage_fig, use_container_width=True)

with col2:
    st.subheader("DC Current Comparison")
    st.caption("Atmoce: I = P/V (calculated)")
    dc_current_fig = go.Figure()
    dc_current_fig.add_trace(go.Scatter(x=atmoce_filtered['Time'], y=atmoce_filtered['PV1 Current (A)'],
        mode='lines', name='Atmoce PV1', line=dict(color=colors['atmoce_pv1'], width=2), connectgaps=False))
    dc_current_fig.add_trace(go.Scatter(x=atmoce_filtered['Time'], y=atmoce_filtered['PV2 Current (A)'],
        mode='lines', name='Atmoce PV2', line=dict(color=colors['atmoce_pv2'], width=2), connectgaps=False))
    dc_current_fig.add_trace(go.Scatter(x=enphase_left['Time'], y=enphase_left['DC Current (A)'],
        mode='lines+markers', name='PVleft (6901)', line=dict(color=colors['enphase_left'], width=2),
        marker=dict(size=4), connectgaps=False))
    dc_current_fig.add_trace(go.Scatter(x=enphase_right['Time'], y=enphase_right['DC Current (A)'],
        mode='lines+markers', name='PVright (6789)', line=dict(color=colors['enphase_right'], width=2),
        marker=dict(size=4), connectgaps=False))
    dc_current_fig.update_layout(xaxis_title='Time', yaxis_title='Current (A)', template='plotly_white', height=350, hovermode='x unified')
    st.plotly_chart(dc_current_fig, use_container_width=True)

# Grid Voltage and Frequency side by side
col1, col2 = st.columns(2)

with col1:
    st.subheader("Grid Voltage Over Time")
    grid_voltage_fig = go.Figure()
    grid_voltage_fig.add_trace(go.Scatter(x=atmoce_filtered['Time'], y=atmoce_filtered['Grid Voltage (V)'],
        mode='lines', name='Atmoce', line=dict(color=colors['atmoce'], width=2), connectgaps=False))
    grid_voltage_fig.add_trace(go.Scatter(x=enphase_agg_filtered['Time'], y=enphase_agg_filtered['Grid Voltage (V)'],
        mode='lines+markers', name='Enphase', line=dict(color=colors['enphase'], width=2),
        marker=dict(size=4), connectgaps=False))
    grid_voltage_fig.add_hline(y=230, line_dash="dash", line_color="gray", annotation_text="Nominal 230V")
    grid_voltage_fig.update_layout(xaxis_title='Time', yaxis_title='Voltage (V)', template='plotly_white', height=350, hovermode='x unified')
    st.plotly_chart(grid_voltage_fig, use_container_width=True)

with col2:
    st.subheader("Grid Frequency Over Time")
    grid_freq_fig = go.Figure()
    grid_freq_fig.add_trace(go.Scatter(x=atmoce_filtered['Time'], y=atmoce_filtered['Frequency (Hz)'],
        mode='lines', name='Atmoce', line=dict(color=colors['atmoce'], width=2), connectgaps=False))
    grid_freq_fig.add_trace(go.Scatter(x=enphase_agg_filtered['Time'], y=enphase_agg_filtered['Frequency (Hz)'],
        mode='lines+markers', name='Enphase', line=dict(color=colors['enphase'], width=2),
        marker=dict(size=4), connectgaps=False))
    grid_freq_fig.add_hline(y=50, line_dash="dash", line_color="gray", annotation_text="Nominal 50Hz")
    grid_freq_fig.update_layout(xaxis_title='Time', yaxis_title='Frequency (Hz)', template='plotly_white', height=350, hovermode='x unified')
    st.plotly_chart(grid_freq_fig, use_container_width=True)

# Footer
st.divider()
st.markdown("*IQ8P 2-pin India Comparison Study | Enphase Energy*")
