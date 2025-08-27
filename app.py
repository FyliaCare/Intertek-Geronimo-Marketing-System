# app_executive_insights_full.py
# Intertek Geronimo — Comprehensive Executive Insights Dashboard (single-file, upgraded)
# Visuals: 3D Radar (regions), 3D Funnel (engagement stages), Color-Segregated Sector Histogram,
#          3D Geographic Heatmap (Ghana-focused) with pydeck ColumnLayer.

import os
import sqlite3
from datetime import datetime, date, timedelta
from io import BytesIO
from typing import List, Dict, Any, Optional

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pydeck as pdk

# -----------------------
# Page config & CSS
# -----------------------
st.set_page_config(page_title="Intertek Geronimo — Executive Insights (Full)", layout="wide", page_icon="📊")

CUSTOM_CSS = """
<style>
.block-container {padding-top: 10px; max-width:1400px;}
.kpi { background: linear-gradient(180deg, rgba(250,250,252,1) 0%, rgba(255,255,255,1) 100%); border: 1px solid #e6e6e6; border-radius: 12px; padding: 12px; box-shadow: 0 1px 6px rgba(0,0,0,0.04); }
.kpi .label {font-size: 0.85rem; color: #6b7280; margin-bottom: 6px;}
.kpi .value {font-size: 1.6rem; font-weight:700}
.alert { padding: 12px; border-radius: 8px; border: 1px solid #fde68a; background: #fffbeb; color:#92400e; }
.section-title {font-weight:700; font-size:16px; margin-bottom:6px;}
.small {font-size:12px; color:#6b7280;}
.stDataFrame {border-radius:10px; overflow:hidden;}
.overdue { color: #b91c1c; font-weight:700; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# -----------------------
# Constants
# -----------------------
DB_PATH = os.environ.get("CRM_DB", "crm_actions.db")

SECTORS = [
    "Oil & Gas / Petroleum Refining & Storage",
    "Power Generation",
    "Mining & Mineral Processing",
    "Steel & Metal Processing",
    "Cement & Building Materials",
    "Food & Beverage Manufacturing",
    "Cocoa & Agro-Processing",
    "Chemicals & Pharmaceuticals",
    "Textiles & Light Manufacturing",
    "LNG / LPG & Fuel Storage",
    "Water Treatment & Utilities",
    "Pulp & Paper / Printing",
    "Shipyards & Marine",
    "Other"
]

REGIONS_GH = [
    "Greater Accra","Ashanti","Western","Western North","Central","Eastern","Volta","Oti",
    "Northern","Savannah","North East","Upper East","Upper West","Bono","Bono East","Ahafo"
]

# Approx region centroids (lat, lon)
REGION_COORDS = {
    'Greater Accra': (5.6037, -0.1870),
    'Ashanti': (6.6666, -1.6163),
    'Western': (4.9167, -1.7607),
    'Western North': (6.6667, -2.2600),
    'Central': (5.1214, -1.3442),
    'Eastern': (6.0455, -0.2474),
    'Volta': (6.5786, 0.4726),
    'Oti': (8.0500, 0.3667),
    'Northern': (9.4008, -0.8393),
    'Savannah': (8.3500, -1.0833),
    'North East': (9.6500, -0.2500),
    'Upper East': (10.6856, -0.2076),
    'Upper West': (10.2833, -2.2333),
    'Bono': (7.7333, -2.0833),
    'Bono East': (7.9000, -1.7333),
    'Ahafo': (7.3500, -2.3000)
}

PRIORITIES = ["Low","Medium","High","Critical"]
STATUSES = ["Open","In Progress","Done","Blocked"]

# -----------------------
# DB helpers
# -----------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def run_sql(sql: str, params: tuple = (), fetch: bool = False, commit: bool = False):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        if commit:
            conn.commit()
        if fetch:
            return cur.fetchall()
        return None

@st.cache_data(show_spinner=False)
def read_sql(sql: str, params: tuple = ()):  # returns DataFrame
    with get_conn() as conn:
        return pd.read_sql(sql, conn, params=params)

def clear_cache_and_refresh():
    st.cache_data.clear()
    st.experimental_rerun()

def df_to_excel_bytes(dfs: Dict[str, pd.DataFrame]) -> bytes:
    out = BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        for sheet, df in dfs.items():
            df.to_excel(writer, sheet_name=sheet[:31], index=False)
    out.seek(0)
    return out.getvalue()

# -----------------------
# DB schema & seed
# -----------------------
def init_db():
    ddl = """
    PRAGMA foreign_keys = ON;
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT NOT NULL,
        sector TEXT,
        region TEXT,
        location TEXT,
        company_size TEXT,
        contact_person TEXT,
        contact_email TEXT,
        contact_phone TEXT,
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS action_points (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        title TEXT NOT NULL,
        description TEXT,
        status TEXT DEFAULT 'Open',
        priority TEXT DEFAULT 'Medium',
        due_date TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        completed_at TEXT,
        tags TEXT,
        FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
    );
    CREATE TABLE IF NOT EXISTS activity_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action_point_id INTEGER,
        prev_status TEXT,
        new_status TEXT,
        note TEXT,
        changed_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (action_point_id) REFERENCES action_points(id) ON DELETE CASCADE
    );
    """
    with get_conn() as conn:
        conn.executescript(ddl)
        conn.commit()

def seed_defaults():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(1) FROM clients")
        if cur.fetchone()[0] == 0:
            demo_clients = [
                ("Latex Foam", "Food & Beverage Manufacturing", "Greater Accra", "Industrial Area - Accra", "Medium", "Mary Amoah", "mary@latex.com", "+233201234567", "Preferred contact via WhatsApp"),
                ("Tema Oil Services", "Oil & Gas / Petroleum Refining & Storage", "Greater Accra", "Tema", "Large", "Kwame Nkrumah", "kwame@temaos.com", "+233501234567", "Key supplier for storage tanks"),
                ("Ocean Fare", "Shipyards & Marine", "Greater Accra", "Tema", "Medium", "John Boateng", "john@oceanfare.com", "+233241234567", "Follow up re: inspection"),
                ("Ashanti Mines", "Mining & Mineral Processing", "Ashanti", "Kumasi", "Large", "Ama Serwaa", "ama@ashantimines.gh", "+233501112233", "Priority account"),
                ("Cocoa Works Ltd", "Cocoa & Agro-Processing", "Eastern", "Koforidua", "Medium", "Kojo Mensah", "kojo@cocoaworks.gh", "+233209876543", "Sampling discussion")
            ]
            cur.executemany("""INSERT INTO clients 
                (company_name, sector, region, location, company_size, contact_person, contact_email, contact_phone, notes) 
                VALUES (?,?,?,?,?,?,?,?,?)""", demo_clients)
            conn.commit()

        cur.execute("SELECT COUNT(1) FROM action_points")
        if cur.fetchone()[0] == 0:
            cur.execute("SELECT id FROM clients")
            crows = cur.fetchall()
            today = date.today()
            ap_rows = []
            tags_pool = [
                "intro,site", "proposal,negotiation", "contract,won",
                "intro", "site,proposal", "negotiation", "proposal", "contract"
            ]
            for i, (cid,) in enumerate(crows):
                ap_rows.append((cid, f"Initial outreach #{i+1}", "Phone call to introduce services", "Open", "High",
                                (today + timedelta(days=3+i)).isoformat(), today.isoformat(), None, tags_pool[i % len(tags_pool)]))
                ap_rows.append((cid, f"Site visit #{i+1}", "Schedule site visit and survey", "In Progress", "Medium",
                                (today + timedelta(days=7+i)).isoformat(), today.isoformat(), None, "site"))
                ap_rows.append((cid, f"Proposal followup #{i+1}", "Review proposal and confirm next steps", "Done", "Medium",
                                (today - timedelta(days=2+i)).isoformat(), (today - timedelta(days=10)).isoformat(),
                                (today - timedelta(days=1)).isoformat(), "proposal"))
            cur.executemany("""INSERT INTO action_points 
                (client_id, title, description, status, priority, due_date, created_at, completed_at, tags) 
                VALUES (?,?,?,?,?,?,?,?,?)""", ap_rows)
            conn.commit()

init_db()
seed_defaults()

# -----------------------
# Cached data readers
# -----------------------
@st.cache_data(show_spinner=False)
def get_clients_df() -> pd.DataFrame:
    df = read_sql("SELECT * FROM clients ORDER BY created_at DESC")
    if not df.empty and 'created_at' in df:
        df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
    return df

@st.cache_data(show_spinner=False)
def get_action_points_df() -> pd.DataFrame:
    df = read_sql(
        """
        SELECT a.*, c.company_name AS company_name, c.sector AS sector, c.region AS region
        FROM action_points a
        LEFT JOIN clients c ON c.id = a.client_id
        ORDER BY date(a.created_at) DESC, a.id DESC
        """
    )
    for col in ["due_date", "created_at", "completed_at"]:
        if col in df:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df

# -----------------------
# Analytics helpers
# -----------------------
def compute_kpis(df_actions: pd.DataFrame, df_clients: pd.DataFrame) -> Dict[str, Any]:
    total_clients = int(df_clients.shape[0])
    active_clients = int(df_actions['company_name'].dropna().nunique()) if not df_actions.empty else 0
    total_actions = int(df_actions.shape[0])
    completed = int((df_actions['status'] == 'Done').sum()) if not df_actions.empty else 0
    completion_rate = round(100 * completed / max(total_actions, 1), 2)
    overdue_mask = (df_actions['due_date'].notna()) & (df_actions['due_date'].dt.date < date.today()) & (df_actions['status'] != 'Done')
    overdue_count = int(overdue_mask.sum())
    avg_actions_per_client = round(total_actions / max(total_clients, 1), 2)
    avg_days = None
    if completed > 0:
        completed_rows = df_actions[df_actions['status']=='Done'].copy()
        completed_rows['days_to_complete'] = (completed_rows['completed_at'].dt.date - completed_rows['created_at'].dt.date).apply(lambda d: d.days if pd.notna(d) else None)
        s = completed_rows['days_to_complete'].dropna()
        if not s.empty:
            avg_days = round(s.mean(), 2)
    return {
        'total_clients': total_clients,
        'active_clients': active_clients,
        'total_actions': total_actions,
        'completed': completed,
        'completion_rate': completion_rate,
        'overdue_count': overdue_count,
        'avg_actions_per_client': avg_actions_per_client,
        'avg_days_to_complete': avg_days
    }

def weekly_progression(df_actions: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if start > end:
        start, end = end, start
    dfa = df_actions.copy()
    dfa['created_date'] = dfa['created_at'].dt.date
    dfa['completed_date'] = dfa['completed_at'].dt.date
    start_dt = pd.to_datetime(start).normalize()
    end_dt = pd.to_datetime(end).normalize()
    week_starts = pd.date_range(start=start_dt, end=end_dt, freq='W-MON')
    if len(week_starts) == 0 or week_starts[0].date() > start:
        week_starts = pd.DatetimeIndex([start_dt]).union(week_starts)
    rows = []
    for wstart in week_starts:
        wstart_date = wstart.date()
        wend_date = (wstart_date + timedelta(days=6))
        created = int(dfa[(dfa['created_date'] >= wstart_date) & (dfa['created_date'] <= wend_date)].shape[0])
        completed = int(dfa[(dfa['completed_date'] >= wstart_date) & (dfa['completed_date'] <= wend_date)].shape[0])
        pct = round(100 * completed / created, 2) if created > 0 else None
        rows.append({'week_start': wstart_date, 'week_end': wend_date, 'created': created, 'completed': completed, 'completion_pct': pct})
    return pd.DataFrame(rows)

def compute_funnel(df_actions: pd.DataFrame, stages: Optional[List[str]] = None) -> pd.DataFrame:
    if stages is None:
        stages = ['intro','site','proposal','negotiation','contract','won']
    text_series = df_actions['tags'].fillna('').astype(str).str.lower()
    rows = [{'stage': s.capitalize(), 'count': int(text_series.str.contains(s).sum())} for s in stages]
    return pd.DataFrame(rows)

def region_engagements(df_actions: pd.DataFrame) -> pd.DataFrame:
    if df_actions.empty:
        return pd.DataFrame(columns=['region','engagements','lat','lon'])
    agg = df_actions.groupby('region').size().reset_index(name='engagements')
    agg['region'] = agg['region'].fillna('Unknown')
    lat, lon = [], []
    for _, r in agg.iterrows():
        coords = REGION_COORDS.get(r['region'], (None, None))
        lat.append(coords[0]); lon.append(coords[1])
    agg['lat'] = lat; agg['lon'] = lon
    return agg.dropna(subset=['lat','lon'])

# -----------------------
# 3D visuals helpers
# -----------------------
def build_funnel_mesh(counts: List[float], heights: Optional[List[float]] = None, radial_scale: float = 1.0):
    if heights is None:
        heights = [1.0] * len(counts)
    maxc = max(counts) if max(counts) > 0 else 1.0
    radii = [radial_scale * (c / maxc) for c in counts]
    nseg = 32
    vx, vy, vz, stage_index = [], [], [], []
    for idx, (r, h) in enumerate(zip(radii, heights)):
        z = sum(heights[:idx])
        for k in range(nseg):
            theta = 2 * np.pi * k / nseg
            vx.append(r * np.cos(theta))
            vy.append(r * np.sin(theta))
            vz.append(z)
            stage_index.append(idx)
    top_z = sum(heights)
    vx.append(0.0); vy.append(0.0); vz.append(top_z); stage_index.append(len(counts))
    faces_i, faces_j, faces_k = [], [], []
    for s in range(len(counts)-1):
        a_off = s * nseg
        b_off = (s+1) * nseg
        for k in range(nseg):
            a0 = a_off + k
            a1 = a_off + (k+1) % nseg
            b0 = b_off + k
            b1 = b_off + (k+1) % nseg
            faces_i += [a0, a0]
            faces_j += [b0, b1]
            faces_k += [b1, a1]
    top_idx = len(vx) - 1
    last_ring_offset = (len(counts)-1)*nseg
    for k in range(nseg):
        a = last_ring_offset + k
        b = last_ring_offset + (k+1) % nseg
        faces_i.append(a); faces_j.append(b); faces_k.append(top_idx)
    return dict(x=vx, y=vy, z=vz, i=faces_i, j=faces_j, k=faces_k, stage_index=stage_index)

def build_region_radar_mesh(reg_counts: pd.DataFrame):
    # reg_counts: columns ['region','engagements']
    # Map each region to an angle on a circle; radius = normalized engagements; create a tent-like 3D Mesh
    if reg_counts.empty:
        return None
    counts = reg_counts['engagements'].to_numpy(dtype=float)
    labels = reg_counts['region'].astype(str).tolist()
    maxc = max(counts) if counts.size > 0 else 1.0
    radii = (counts / max(maxc, 1.0)) + 0.1  # add base so zeroes still visible
    n = len(radii)
    angles = np.linspace(0, 2*np.pi, n, endpoint=False)

    # Rim points
    vx, vy, vz = [], [], []
    colors_val = []
    for r, th, c in zip(radii, angles, counts):
        x = r * np.cos(th)
        y = r * np.sin(th)
        z = r  # give vertical relief proportional to intensity
        vx.append(x); vy.append(y); vz.append(z); colors_val.append(c)

    # Close the loop for faces by repeating first point
    vx.append(vx[0]); vy.append(vy[0]); vz.append(vz[0]); colors_val.append(colors_val[0])

    # Add center point (slightly below for concave look)
    cx, cy, cz = 0.0, 0.0, 0.0
    vx.append(cx); vy.append(cy); vz.append(cz)
    center_idx = len(vx) - 1

    # Triangulate fan from center to rim
    faces_i, faces_j, faces_k = [], [], []
    for k in range(n):
        a = k
        b = k + 1
        faces_i.append(center_idx); faces_j.append(a); faces_k.append(b)

    # Color per face using average of vertices (approx via colors_val per rim)
    face_color = [ (colors_val[k] + colors_val[(k+1)%n]) / 2.0 for k in range(n) ]

    mesh = dict(x=vx, y=vy, z=vz, i=faces_i, j=faces_j, k=faces_k, face_color=face_color, labels=labels, counts=counts)
    return mesh

# -----------------------
# Sidebar & Navigation
# -----------------------
st.sidebar.title("Intertek Geronimo — Executive Dashboard (Full)")
nav = st.sidebar.radio("Navigate to", ["Executive Insights","Clients","Action Points","Reports & Export"])
st.sidebar.markdown("---")

# Global filters
sector_filter = st.sidebar.multiselect("Sector (filter)", options=SECTORS)
region_filter = st.sidebar.multiselect("Region (filter)", options=REGIONS_GH)
start_date = st.sidebar.date_input("Start date", value=date.today() - timedelta(days=180))
end_date = st.sidebar.date_input("End date", value=date.today())
top_n = st.sidebar.slider("Top N clients", min_value=5, max_value=50, value=10)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Reset cached data"):
    clear_cache_and_refresh()

# Load data
clients = get_clients_df()
actions = get_action_points_df()

# Apply global filters
filtered_clients = clients.copy()
filtered_actions = actions.copy()
if sector_filter:
    filtered_clients = filtered_clients[filtered_clients['sector'].isin(sector_filter)]
    filtered_actions = filtered_actions[filtered_actions['sector'].isin(sector_filter)]
if region_filter:
    filtered_clients = filtered_clients[filtered_clients['region'].isin(region_filter)]
    filtered_actions = filtered_actions[filtered_actions['region'].isin(region_filter)]
if 'created_at' in filtered_actions.columns:
    filtered_actions = filtered_actions[(filtered_actions['created_at'].dt.date >= start_date) & (filtered_actions['created_at'].dt.date <= end_date)]

# -----------------------
# Pages
def page_executive_insights():
    # Comprehensive, corrected Executive Insights page
    # - Uses filtered_actions and filtered_clients (from global scope)
    # - Robust handling of date columns and missing data
    # - KPIs, Weekly progression, Sector histogram (color-segregated)
    # - 3D Regional Radar (Mesh3D)
    # - 2D Ghana regional hotspots (map) + 2D Proposal funnel (side-by-side)
    # - Grouped task-style action log with checkboxes
    import math
    from datetime import datetime as _dt, timedelta as _td

    # safe copies
    df_actions = filtered_actions.copy() if 'filtered_actions' in globals() else pd.DataFrame()
    df_clients = filtered_clients.copy() if 'filtered_clients' in globals() else pd.DataFrame()

    # normalize datetime columns
    for col in ['created_at', 'due_date', 'completed_at']:
        if col in df_actions.columns:
            df_actions[col] = pd.to_datetime(df_actions[col], errors='coerce')

    # create a canonical action_date column (prefer created_at)
    if 'created_at' in df_actions.columns:
        df_actions['action_date'] = pd.to_datetime(df_actions['created_at'], errors='coerce')
    elif 'date' in df_actions.columns:
        df_actions['action_date'] = pd.to_datetime(df_actions['date'], errors='coerce')
    else:
        # no date-like column found
        df_actions['action_date'] = pd.NaT

    # Use sidebar start_date / end_date if available, else sensible defaults
    _today = _dt.now()
    ins_start = globals().get('start_date', None)
    ins_end = globals().get('end_date', None)

    if ins_start is None:
        # default to 180 days back or earliest action_date
        if not df_actions['action_date'].isna().all():
            ins_start = df_actions['action_date'].min()
        else:
            ins_start = _today - _td(days=180)
    if ins_end is None:
        ins_end = _today

    ins_start = pd.to_datetime(ins_start)
    ins_end = pd.to_datetime(ins_end)

    # ensure inclusive end of day
    ins_end_inclusive = ins_end + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)

    # Filter actions to the selected window
    mask_time = df_actions['action_date'].notna() & (df_actions['action_date'] >= ins_start) & (df_actions['action_date'] <= ins_end_inclusive)
    df = df_actions[mask_time].copy()

    st.markdown("# 🧭 Executive Insights — Visual Suite")
    st.caption("KPIs, weekly progression, sector histogram, 3D regional radar, Ghana hotspots (2D), 2D proposal funnel, and grouped task log.")

    # ---------- KPIs ----------
    k = compute_kpis(df, df_clients) if 'compute_kpis' in globals() else {
        'total_clients': df_clients.shape[0],
        'active_clients': df['company_name'].nunique() if not df.empty else 0,
        'total_actions': df.shape[0],
        'completed': int((df['status']=='Done').sum()) if 'status' in df.columns else 0,
        'completion_rate': round(100 * (df['status']=='Done').sum() / max(df.shape[0],1),2) if not df.empty and 'status' in df.columns else 0,
        'overdue_count': 0,
        'avg_actions_per_client': round(df.shape[0]/max(df_clients.shape[0],1),2),
        'avg_days_to_complete': None
    }

    cols = st.columns([1.4,1.0,1.0,1.0,1.0,1.0])
    def kcard(col, label, value, help_text=None):
        with col:
            st.markdown(f"<div class='kpi'><div class='label'>{label}</div><div class='value'>{value}</div><div class='small'>{help_text or ''}</div></div>", unsafe_allow_html=True)
    kcard(cols[0], "Total Clients", k['total_clients'], "All clients in system")
    kcard(cols[1], "Active Clients", k['active_clients'], "Clients with ≥1 action")
    kcard(cols[2], "Total Actions", k['total_actions'])
    kcard(cols[3], "Completion Rate", f"{k['completion_rate']}%", "% marked Done")
    kcard(cols[4], "Overdue", k['overdue_count'], "Open actions past due")
    kcard(cols[5], "Avg days to complete", k.get('avg_days_to_complete') or '—', "Completed actions")

    st.markdown("---")

    # ---------- Two-column top area: Weekly trend + Sector histogram | 3D Radar ----------
    left_col, right_col = st.columns([1.4,1.0])

    # Weekly Created vs Completed (left)
    with left_col:
        st.subheader("📈 Weekly Created vs Completed")
        try:
            prog_df = weekly_progression(df, ins_start.date(), ins_end.date()) if 'weekly_progression' in globals() else pd.DataFrame()
        except Exception:
            prog_df = pd.DataFrame()
        if prog_df.empty:
            st.info("No weekly progression data for the selected range.")
        else:
            fig_line = px.line(prog_df, x='week_start', y=['created','completed'], markers=True,
                               labels={'week_start':'Week start','value':'Count','variable':'Metric'},
                               title='Weekly Created vs Completed')
            fig_line.update_traces(mode='markers+lines')
            fig_line.update_layout(legend_title_text='Metric', height=340, margin=dict(l=10,r=10,t=40,b=10))
            st.plotly_chart(fig_line, use_container_width=True)

        st.subheader("🏭 Engagements by Sector (Color Segregated)")
        if df.empty or 'sector' not in df.columns:
            st.info("No action data to summarize by sector.")
        else:
            sector_counts = df.groupby('sector').size().reset_index(name='engagements').sort_values('engagements', ascending=False)
            fig_bar = px.bar(sector_counts, x='sector', y='engagements', color='sector', title='Engagements by Sector', text='engagements')
            fig_bar.update_layout(xaxis_title='', yaxis_title='Engagements', showlegend=False, height=360, margin=dict(l=10,r=10,t=40,b=100))
            fig_bar.update_xaxes(tickangle=-35)
            st.plotly_chart(fig_bar, use_container_width=True)

    # 3D Regional Radar (right)
    with right_col:
        st.subheader("🌐 Regional Comparison — 3D Radar")
        if df.empty or 'region' not in df.columns:
            st.info("No regional engagement data.")
        else:
            reg = df.groupby('region').size().reset_index(name='engagements').dropna().sort_values('engagements', ascending=False)
            mesh = build_region_radar_mesh(reg) if 'build_region_radar_mesh' in globals() else None
            if mesh is None:
                st.info("Not enough data for 3D radar.")
            else:
                fig_radar3d = go.Figure(data=[
                    go.Mesh3d(
                        x=mesh['x'], y=mesh['y'], z=mesh['z'],
                        i=mesh['i'], j=mesh['j'], k=mesh['k'],
                        intensity=mesh.get('face_color', mesh.get('counts', [0]*len(mesh.get('i',[])))),
                        colorscale='Turbo', showscale=True, opacity=0.9
                    )
                ])
                fig_radar3d.update_layout(scene=dict(xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False), aspectmode='data'),
                                          margin=dict(l=0, r=0, t=30, b=0), height=420,
                                          title="3D Radar Surface of Regional Engagements")
                st.plotly_chart(fig_radar3d, use_container_width=True)

    st.markdown("---")

    # ---------- Map (2D) + Funnel (2D) side-by-side ----------
    st.subheader("Regional Engagement & Proposal Funnel")
    col_map, col_funnel = st.columns(2)

    # Map: Ghana hotspots (2D) using region centroids from REGION_COORDS -> scatter_mapbox bubbles
    with col_map:
        st.markdown("**Geographic Engagement Heatmap — Ghana (2D)**")
        reg_geo = region_engagements(df) if 'region_engagements' in globals() else pd.DataFrame()
        if reg_geo.empty:
            st.info("No regional positions available.")
        else:
            # Make sure lat/lon numeric
            reg_geo = reg_geo.copy()
            reg_geo['lat'] = pd.to_numeric(reg_geo['lat'], errors='coerce')
            reg_geo['lon'] = pd.to_numeric(reg_geo['lon'], errors='coerce')
            reg_geo = reg_geo.dropna(subset=['lat','lon'])
            if reg_geo.empty:
                st.info("No valid region coordinates.")
            else:
                center = {'lat': reg_geo['lat'].mean(), 'lon': reg_geo['lon'].mean()}
                # normalize size
                max_e = max(reg_geo['engagements'].max(), 1)
                reg_geo['size'] = reg_geo['engagements'] / max_e * 40 + 6
                fig_map = px.scatter_mapbox(reg_geo, lat='lat', lon='lon', size='size', color='engagements',
                                           hover_name='region', hover_data={'engagements':True, 'lat':False, 'lon':False, 'size':False},
                                           center=center, zoom=5.4, title='Ghana Regional Engagement Hotspots',
                                           color_continuous_scale='YlOrRd')
                fig_map.update_layout(mapbox_style='open-street-map', margin=dict(l=0,r=0,t=30,b=0), height=480)
                st.plotly_chart(fig_map, use_container_width=True)

    # Funnel (2D) built from tags via compute_funnel()
    with col_funnel:
        st.markdown("**Proposal Engagement Funnel (2D)**")
        if df.empty:
            st.info("No actions to build funnel.")
        else:
            funnel_df = compute_funnel(df) if 'compute_funnel' in globals() else pd.DataFrame({'stage':['Intro','Site','Proposal','Negotiation','Contract','Won'], 'count':[0,0,0,0,0,0]})
            if funnel_df.empty:
                st.info("No funnel data.")
            else:
                # ensure columns: stage, count
                funnel_df = funnel_df.rename(columns={funnel_df.columns[0]:'stage', funnel_df.columns[1]:'count'}) if funnel_df.shape[1]>=2 else funnel_df
                fig_funnel2d = px.funnel(funnel_df, x='count', y='stage', color='stage',
                                         color_discrete_sequence=px.colors.sequential.Viridis)
                fig_funnel2d.update_layout(margin=dict(l=0,r=0,t=30,b=0), height=480)
                st.plotly_chart(fig_funnel2d, use_container_width=True)

    st.markdown("---")

    # ---------- Task Log (Grouped, checkbox style) ----------
    st.subheader("📝 Proposal / Action Engagement Tasks")

    # Reuse the ins_start/ins_end filter window (already applied to df)
    df_tasks = df.copy()
    if df_tasks.empty:
        st.info("No actions logged for the selected period.")
    else:
        # infer action_type from tags/title/status
        def infer_action_type(row):
            t = str(row.get('tags','') or '').lower()
            title = str(row.get('title','') or '').lower()
            status = str(row.get('status','') or '').lower()
            if 'proposal' in t or 'proposal' in title:
                return 'Proposal'
            if 'site' in t or 'site' in title or 'visit' in title:
                return 'Site Visit'
            if 'intro' in t or 'intro' in title or 'introduc' in title:
                return 'Intro'
            if 'negoti' in t or 'negoti' in title:
                return 'Negotiation'
            if 'contract' in t or 'won' in t or status in ('done','closed'):
                return 'Closed'
            if status:
                return status.capitalize()
            return 'Other'

        df_tasks['action_type'] = df_tasks.apply(infer_action_type, axis=1)
        # icons for better visual cue
        icons = {'Proposal':'📄','Site Visit':'📍','Intro':'👋','Negotiation':'💬','Closed':'✅','Open':'🔔','In Progress':'⏳','Other':'•'}

        # Group and display
        grouped = df_tasks.groupby('action_type')
        # Sort groups by a priority list (nice ordering)
        priority_order = ['Proposal','Site Visit','Intro','Negotiation','Closed','In Progress','Open','Other']
        groups_sorted = sorted(grouped, key=lambda g: priority_order.index(g[0]) if g[0] in priority_order else len(priority_order))

        for action_type, group in groups_sorted:
            st.markdown(f"### {icons.get(action_type,'•')} {action_type}")
            for _, row in group.sort_values('action_date', ascending=False).iterrows():
                rid = int(row['id']) if 'id' in row and not pd.isna(row['id']) else f"r{hash(row.get('title','')+str(row.get('company_name','')))%100000}"
                company = row.get('company_name') or row.get('contact_person') or 'Unknown'
                title_text = (row.get('title') or '').strip()
                date_val = row.get('action_date')
                if pd.isna(date_val):
                    date_str = '—'
                else:
                    try:
                        date_str = pd.to_datetime(date_val).strftime("%b %d, %Y")
                    except Exception:
                        date_str = str(date_val)
                note = (row.get('description') or row.get('notes') or row.get('tags') or '').strip()
                # Friendly task wording:
                text = f"**{title_text or action_type}** — {company} • *{date_str}*"
                if note:
                    text += f" — {note}"
                st.checkbox(text, value=False, key=f"task_{rid}")

    st.markdown("---")

    # ---------- Top clients ----------
    st.subheader(f"🏆 Top {top_n if 'top_n' in globals() else 10} Clients by Engagements")
    if df.empty or 'company_name' not in df.columns:
        st.info("No actions to rank clients.")
    else:
        top_clients = df.groupby('company_name').size().reset_index(name='engagements').sort_values('engagements', ascending=False).head(top_n if 'top_n' in globals() else 10)
        st.dataframe(top_clients, use_container_width=True, height=300)


def page_clients():
    st.markdown("# 👥 Clients — Directory & Management")
    st.caption("Maintain client master data and contacts")

    # Quick search
    ql = st.text_input("Quick search (company / contact / phone)").strip().lower()
    df = clients.copy()
    if ql:
        df = df[
            df['company_name'].str.lower().str.contains(ql) |
            df['contact_person'].fillna("").str.lower().str.contains(ql) |
            df['contact_phone'].fillna("").str.lower().str.contains(ql)
        ]
    st.dataframe(df, use_container_width=True, height=320)

    st.markdown("---")
    st.subheader("Add / Edit Client")
    client_options = ["— New Client —"] + [f"{r['company_name']} (id:{int(r['id'])})" for _, r in clients.iterrows()]
    sel = st.selectbox("Select client to edit", options=client_options)
    edit_id = None
    if sel and sel != "— New Client —":
        try:
            edit_id = int(sel.split("id:")[-1].strip().strip(')'))
        except Exception:
            edit_id = None

    if edit_id:
        row = clients[clients['id']==edit_id].iloc[0]
        default_name = row['company_name']
        default_sector = row['sector'] if not pd.isna(row['sector']) else SECTORS[0]
        default_region = row['region'] if not pd.isna(row['region']) else REGIONS_GH[0]
        default_location = row['location'] if not pd.isna(row['location']) else ''
        default_size = row['company_size'] if not pd.isna(row['company_size']) else 'Medium'
        default_contact = row['contact_person'] if not pd.isna(row['contact_person']) else ''
        default_email = row['contact_email'] if not pd.isna(row['contact_email']) else ''
        default_phone = row['contact_phone'] if not pd.isna(row['contact_phone']) else ''
        default_notes = row['notes'] if not pd.isna(row['notes']) else ''
    else:
        default_name = ''
        default_sector = SECTORS[0]
        default_region = REGIONS_GH[0]
        default_location = ''
        default_size = 'Medium'
        default_contact = ''
        default_email = ''
        default_phone = ''
        default_notes = ''

    with st.form("client_form", clear_on_submit=False):
        company_name = st.text_input("Company name *", value=default_name)
        sector = st.selectbox("Sector", options=SECTORS, index=SECTORS.index(default_sector) if default_sector in SECTORS else 0)
        region = st.selectbox("Region", options=REGIONS_GH, index=REGIONS_GH.index(default_region) if default_region in REGIONS_GH else 0)
        location = st.text_input("Location / City", value=default_location)
        company_size = st.selectbox("Company size", options=["Small","Medium","Large"], index=["Small","Medium","Large"].index(default_size) if default_size in ["Small","Medium","Large"] else 1)
        contact_person = st.text_input("Contact person", value=default_contact)
        contact_email = st.text_input("Contact email", value=default_email)
        contact_phone = st.text_input("Contact phone", value=default_phone)
        notes = st.text_area("Notes", value=default_notes)

        if st.form_submit_button("Save client"):
            if not company_name.strip():
                st.error("Company name is required.")
            else:
                if edit_id:
                    run_sql("""UPDATE clients SET company_name=?, sector=?, region=?, location=?, company_size=?,
                               contact_person=?, contact_email=?, contact_phone=?, notes=? WHERE id=?""",
                            (company_name.strip(), sector, region, location.strip(), company_size, contact_person.strip(),
                             contact_email.strip(), contact_phone.strip(), notes.strip(), edit_id), commit=True)
                    st.success("Client updated.")
                else:
                    run_sql("""INSERT INTO clients (company_name, sector, region, location, company_size, contact_person, contact_email, contact_phone, notes)
                               VALUES (?,?,?,?,?,?,?,?,?)""",
                            (company_name.strip(), sector, region, location.strip(), company_size, contact_person.strip(),
                             contact_email.strip(), contact_phone.strip(), notes.strip()), commit=True)
                    st.success("Client added.")
                clear_cache_and_refresh()

    if edit_id:
        st.markdown("---")
        if st.button("Delete this client (permanent)"):
            if st.checkbox("Confirm delete client (this will remove related action points)"):
                run_sql("DELETE FROM clients WHERE id=?", (edit_id,), commit=True)
                st.success("Client deleted.")
                clear_cache_and_refresh()

def page_action_points():
    st.markdown("# ✅ Action Points — Create & Manage Tasks")
    st.caption("Create action points, update status and track progression.")

    # Create
    st.subheader("Create new action point")
    with st.form("create_action", clear_on_submit=True):
        client_sel = st.selectbox("Client", options=["— Select client —"] + [f"{r['company_name']} (id:{int(r['id'])})" for _, r in clients.iterrows()])
        client_id = int(client_sel.split("id:")[-1].strip().strip(')')) if (client_sel and client_sel != "— Select client —") else None
        title = st.text_input("Title *")
        description = st.text_area("Description")
        due_date = st.date_input("Due date", value=date.today() + timedelta(days=7))
        priority = st.selectbox("Priority", options=PRIORITIES, index=1)
        status = st.selectbox("Status", options=STATUSES, index=0)
        tags = st.text_input("Tags (comma separated)")
        if st.form_submit_button("Create action point"):
            if not title.strip():
                st.error("Title required.")
            else:
                run_sql("""INSERT INTO action_points (client_id, title, description, status, priority, due_date, tags)
                           VALUES (?,?,?,?,?,?,?)""",
                        (client_id, title.strip(), description.strip() or None, status, priority,
                         due_date.isoformat() if due_date else None, tags.strip() or None), commit=True)
                st.success("Action point created.")
                clear_cache_and_refresh()

    st.markdown("---")
    st.subheader("Edit / Update action point")
    actions_df = get_action_points_df()
    if actions_df.empty:
        st.info("No action points available.")
        return

    sel_opts = [f"{r['id']}: {r['title']} — {r['company_name'] if not pd.isna(r['company_name']) else '—'}" for _, r in actions_df.iterrows()]
    sel_action = st.selectbox("Select action to edit", options=["— Select —"] + sel_opts)
    if sel_action and sel_action != "— Select —":
        aid = int(sel_action.split(":")[0])
        row = actions_df[actions_df['id']==aid].iloc[0]

        with st.form("edit_action", clear_on_submit=False):
            st.write(f"**ID:** {aid}")
            title_e = st.text_input("Title", value=row['title'])
            desc_e = st.text_area("Description", value=row['description'] if not pd.isna(row['description']) else '')
            due_e = st.date_input("Due date", value=row['due_date'].date() if not pd.isna(row['due_date']) else date.today())
            priority_e = st.selectbox("Priority", options=PRIORITIES, index=(PRIORITIES.index(row['priority']) if (not pd.isna(row['priority']) and row['priority'] in PRIORITIES) else 1))
            status_e = st.selectbox("Status", options=STATUSES, index=(STATUSES.index(row['status']) if (not pd.isna(row['status']) and row['status'] in STATUSES) else 0))
            tags_e = st.text_input("Tags (comma separated)", value=row['tags'] if not pd.isna(row['tags']) else '')
            note_change = st.text_area("Change note (optional)")
            if st.form_submit_button("Save changes"):
                prev_status = row['status']
                completed_at_val = row['completed_at']
                if status_e == 'Done' and (pd.isna(row['completed_at']) or str(row['completed_at']).strip()=='' ):
                    completed_at_val = date.today().isoformat()
                elif status_e != 'Done':
                    completed_at_val = None
                run_sql("""UPDATE action_points SET title=?, description=?, due_date=?, priority=?, status=?, completed_at=?, tags=? WHERE id=?""",
                        (title_e.strip(), desc_e.strip() or None, due_e.isoformat() if due_e else None, priority_e, status_e, completed_at_val, tags_e.strip() or None, aid), commit=True)
                if prev_status != status_e or (note_change and note_change.strip()):
                    run_sql("INSERT INTO activity_logs (action_point_id, prev_status, new_status, note) VALUES (?,?,?,?)",
                            (aid, prev_status, status_e, note_change.strip() or None), commit=True)
                st.success("Action point updated.")
                clear_cache_and_refresh()

        if st.button("Delete this action point"):
            if st.checkbox("Confirm delete action (permanent)"):
                run_sql("DELETE FROM action_points WHERE id=?", (aid,), commit=True)
                st.success("Action point deleted.")
                clear_cache_and_refresh()

def page_reports_and_export():
    st.markdown("# 📤 Reports & Export")
    st.caption("Export datasets, snapshots and quick analytics.")

    dfc = get_clients_df()
    dfa = get_action_points_df()

    c1,c2,c3 = st.columns(3)
    c1.download_button("Download Clients (CSV)", data=dfc.to_csv(index=False).encode('utf-8'), file_name='clients.csv')
    c2.download_button("Download Actions (CSV)", data=dfa.to_csv(index=False).encode('utf-8'), file_name='actions.csv')
    excel_bytes = df_to_excel_bytes({"Clients": dfc, "Actions": dfa})
    c3.download_button("Download Full Excel", data=excel_bytes, file_name=f"Intertek_Actions_{date.today().isoformat()}.xlsx", mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    st.markdown("---")
    st.subheader("Quick snapshots")
    snap = st.selectbox("Snapshot", options=["Open actions by sector","Overdue actions","Actions by tag","Actions by region","Top clients"])
    if st.button("Generate snapshot"):
        if snap == 'Open actions by sector':
            df_snap = dfa[dfa['status']!='Done'].groupby('sector').size().reset_index(name='open_actions').sort_values('open_actions', ascending=False)
            st.table(df_snap)
        elif snap == 'Overdue actions':
            overdue_mask = (dfa['due_date'].notna()) & (dfa['due_date'].dt.date < date.today()) & (dfa['status'] != 'Done')
            df_snap = dfa.loc[overdue_mask][['company_name','title','due_date','priority']]
            st.dataframe(df_snap, use_container_width=True, height=350)
        elif snap == 'Actions by tag':
            rows = []
            for _, r in dfa.iterrows():
                t = r['tags'] if pd.notna(r['tags']) else ''
                for tag in [x.strip() for x in t.split(',') if x.strip()]:
                    rows.append({'id': r['id'], 'company_name': r['company_name'], 'tag': tag})
            df_tags = pd.DataFrame(rows)
            if df_tags.empty:
                st.info('No tags present in actions.')
            else:
                st.table(df_tags.groupby('tag').size().reset_index(name='count').sort_values('count', ascending=False))
        elif snap == 'Actions by region':
            st.table(dfa.groupby('region').size().reset_index(name='count').sort_values('count', ascending=False))
        else:
            st.table(dfa.groupby('company_name').size().reset_index(name='engagements').sort_values('engagements', ascending=False).head(20))

# -----------------------
# Router
# -----------------------
page_map = {
    'Executive Insights': page_executive_insights,
    'Clients': page_clients,
    'Action Points': page_action_points,
    'Reports & Export': page_reports_and_export
}
page_map.get(nav, page_executive_insights)()

# -----------------------
# Footer
# -----------------------
st.markdown("<hr style='margin-top:18px'/>", unsafe_allow_html=True)
st.markdown("<div style='text-align:center; color:#6b7280;'>Built by Jojo Montford — Intertek Geronimo Sales (Ghana) • Full Executive Insights (3D)</div>", unsafe_allow_html=True)
