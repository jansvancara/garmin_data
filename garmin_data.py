import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
from garminconnect import Garmin
import json
import sqlite3
from pathlib import Path
import shutil
import os
import platform
import glob
import csv

# Page configuration
st.set_page_config(
    page_title="Garmin + Browser Stress Analyzer",
    page_icon="❤️",
    layout="wide"
)

# Session state
if 'garmin_client' not in st.session_state:
    st.session_state.garmin_client = None
if 'garmin_data' not in st.session_state:
    st.session_state.garmin_data = None
if 'browser_data' not in st.session_state:
    st.session_state.browser_data = None


def login_garmin(email, password):
    """Login to Garmin Connect"""
    try:
        client = Garmin(email, password)
        client.login()
        st.session_state.garmin_client = client
        return True, "Successfully logged in!"
    except Exception as e:
        return False, f"Login error: {str(e)}"


def get_garmin_data(days=7):
    """Fetch data from Garmin Connect"""
    if not st.session_state.garmin_client:
        return None

    try:
        client = st.session_state.garmin_client
        data_list = []

        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")

            try:
                heart_rate = client.get_heart_rates(date_str)
                stress = client.get_stress_data(date_str)

                if heart_rate and 'heartRateValues' in heart_rate:
                    for hr_point in heart_rate['heartRateValues']:
                        if hr_point[1] is not None:
                            timestamp = hr_point[0] / 1000
                            data_list.append({
                                'timestamp': datetime.fromtimestamp(timestamp),
                                'heart_rate': hr_point[1],
                                'stress': None
                            })

                if stress and 'stressValuesArray' in stress:
                    for stress_point in stress['stressValuesArray']:
                        if stress_point[1] is not None and stress_point[1] >= 0:
                            timestamp = stress_point[0] / 1000
                            data_list.append({
                                'timestamp': datetime.fromtimestamp(timestamp),
                                'heart_rate': None,
                                'stress': stress_point[1]
                            })
            except:
                continue

        if data_list:
            df = pd.DataFrame(data_list)
            df = df.sort_values('timestamp')
            df = df.groupby('timestamp').agg({
                'heart_rate': 'first',
                'stress': 'first'
            }).reset_index()
            return df
        return None
    except Exception as e:
        st.error(f"Error fetching data: {str(e)}")
        return None


def find_browser_history_paths():
    """Auto-detect browser history file paths"""
    system = platform.system()
    paths = {
        'chrome': [],
        'firefox': [],
        'edge': [],
        'opera': [],
        'brave': []
    }

    if system == "Windows":
        chrome_path = os.path.join(os.getenv('LOCALAPPDATA'), 'Google', 'Chrome', 'User Data', 'Default', 'History')
        if os.path.exists(chrome_path):
            paths['chrome'].append(chrome_path)

        firefox_base = os.path.join(os.getenv('APPDATA'), 'Mozilla', 'Firefox', 'Profiles')
        if os.path.exists(firefox_base):
            firefox_profiles = glob.glob(os.path.join(firefox_base, '*.default*', 'places.sqlite'))
            paths['firefox'].extend(firefox_profiles)

        edge_path = os.path.join(os.getenv('LOCALAPPDATA'), 'Microsoft', 'Edge', 'User Data', 'Default', 'History')
        if os.path.exists(edge_path):
            paths['edge'].append(edge_path)

        opera_path = os.path.join(os.getenv('APPDATA'), 'Opera Software', 'Opera Stable', 'History')
        if os.path.exists(opera_path):
            paths['opera'].append(opera_path)

        brave_path = os.path.join(os.getenv('LOCALAPPDATA'), 'BraveSoftware', 'Brave-Browser', 'User Data', 'Default', 'History')
        if os.path.exists(brave_path):
            paths['brave'].append(brave_path)

    elif system == "Darwin":  # macOS
        home = os.path.expanduser("~")

        chrome_path = os.path.join(home, 'Library', 'Application Support', 'Google', 'Chrome', 'Default', 'History')
        if os.path.exists(chrome_path):
            paths['chrome'].append(chrome_path)

        firefox_base = os.path.join(home, 'Library', 'Application Support', 'Firefox', 'Profiles')
        if os.path.exists(firefox_base):
            firefox_profiles = glob.glob(os.path.join(firefox_base, '*.default*', 'places.sqlite'))
            paths['firefox'].extend(firefox_profiles)

        edge_path = os.path.join(home, 'Library', 'Application Support', 'Microsoft Edge', 'Default', 'History')
        if os.path.exists(edge_path):
            paths['edge'].append(edge_path)

        opera_path = os.path.join(home, 'Library', 'Application Support', 'com.operasoftware.Opera', 'History')
        if os.path.exists(opera_path):
            paths['opera'].append(opera_path)

        brave_path = os.path.join(home, 'Library', 'Application Support', 'BraveSoftware', 'Brave-Browser', 'Default', 'History')
        if os.path.exists(brave_path):
            paths['brave'].append(brave_path)

    elif system == "Linux":
        home = os.path.expanduser("~")

        chrome_path = os.path.join(home, '.config', 'google-chrome', 'Default', 'History')
        if os.path.exists(chrome_path):
            paths['chrome'].append(chrome_path)

        firefox_base = os.path.join(home, '.mozilla', 'firefox')
        if os.path.exists(firefox_base):
            firefox_profiles = glob.glob(os.path.join(firefox_base, '*.default*', 'places.sqlite'))
            paths['firefox'].extend(firefox_profiles)

        opera_path = os.path.join(home, '.config', 'opera', 'History')
        if os.path.exists(opera_path):
            paths['opera'].append(opera_path)

        brave_path = os.path.join(home, '.config', 'BraveSoftware', 'Brave-Browser', 'Default', 'History')
        if os.path.exists(brave_path):
            paths['brave'].append(brave_path)

    return paths


def parse_chrome_history(history_path):
    """Read history from Chrome/Edge/Brave"""
    try:
        temp_db = "temp_history.db"
        shutil.copy2(history_path, temp_db)

        conn = sqlite3.connect(temp_db)
        query = """
        SELECT 
            url,
            title,
            datetime(last_visit_time/1000000-11644473600, 'unixepoch', 'localtime') as visit_time
        FROM urls
        WHERE last_visit_time > 0
        ORDER BY last_visit_time DESC
        LIMIT 10000
        """
        df = pd.read_sql_query(query, conn)
        conn.close()

        Path(temp_db).unlink()

        df['visit_time'] = pd.to_datetime(df['visit_time'])
        df['domain'] = df['url'].apply(lambda x: x.split('/')[2] if len(x.split('/')) > 2 else x)
        return df
    except Exception as e:
        st.error(f"Error reading Chrome history: {str(e)}")
        return None


def parse_firefox_history(history_path):
    """Read history from Firefox"""
    try:
        temp_db = "temp_firefox_history.db"
        shutil.copy2(history_path, temp_db)

        conn = sqlite3.connect(temp_db)
        query = """
        SELECT 
            url,
            title,
            datetime(visit_date/1000000, 'unixepoch', 'localtime') as visit_time
        FROM moz_places p
        JOIN moz_historyvisits h ON p.id = h.place_id
        WHERE visit_date > 0
        ORDER BY visit_date DESC
        LIMIT 10000
        """
        df = pd.read_sql_query(query, conn)
        conn.close()

        Path(temp_db).unlink()

        df['visit_time'] = pd.to_datetime(df['visit_time'])
        df['domain'] = df['url'].apply(lambda x: x.split('/')[2] if len(x.split('/')) > 2 else x)
        return df
    except Exception as e:
        st.error(f"Error reading Firefox history: {str(e)}")
        return None


def parse_exported_json(json_data):
    """Parse from JSON export (Chrome History Export, History Trends Unlimited, etc.)"""
    try:
        if isinstance(json_data, str):
            data = json.loads(json_data)
        else:
            data = json_data

        records = []

        if isinstance(data, list):
            for item in data:
                if 'url' in item and 'lastVisitTime' in item:
                    records.append({
                        'url': item.get('url', ''),
                        'title': item.get('title', ''),
                        'visit_time': item.get('lastVisitTime', item.get('time', ''))
                    })
                elif 'url' in item and 'time' in item:
                    records.append({
                        'url': item.get('url', ''),
                        'title': item.get('title', ''),
                        'visit_time': item.get('time', '')
                    })
        elif isinstance(data, dict) and 'history' in data:
            for item in data['history']:
                records.append({
                    'url': item.get('url', ''),
                    'title': item.get('title', ''),
                    'visit_time': item.get('lastVisitTime', item.get('time', ''))
                })

        if records:
            df = pd.DataFrame(records)
            df['visit_time'] = pd.to_datetime(df['visit_time'], unit='ms', errors='coerce')
            df['visit_time'] = df['visit_time'].fillna(pd.to_datetime(df['visit_time'], errors='coerce'))
            df = df.dropna(subset=['visit_time'])
            df['domain'] = df['url'].apply(lambda x: x.split('/')[2] if len(x.split('/')) > 2 else x)
            return df
        return None
    except Exception as e:
        st.error(f"Error reading JSON: {str(e)}")
        return None


def parse_exported_csv(csv_data):
    """Parse from CSV export"""
    try:
        df = pd.read_csv(csv_data)

        url_col = None
        time_col = None
        title_col = None

        for col in df.columns:
            col_lower = col.lower()
            if 'url' in col_lower:
                url_col = col
            elif 'time' in col_lower or 'date' in col_lower or 'visit' in col_lower:
                time_col = col
            elif 'title' in col_lower or 'name' in col_lower:
                title_col = col

        if not url_col or not time_col:
            st.error("CSV must contain 'url' and 'time' columns (or similar)")
            return None

        df = df.rename(columns={
            url_col: 'url',
            time_col: 'visit_time',
            **(({title_col: 'title'}) if title_col else {})
        })

        if 'title' not in df.columns:
            df['title'] = ''

        df['visit_time'] = pd.to_datetime(df['visit_time'], errors='coerce')
        df = df.dropna(subset=['visit_time'])
        df['domain'] = df['url'].apply(lambda x: x.split('/')[2] if len(x.split('/')) > 2 else x)

        return df[['url', 'title', 'visit_time', 'domain']]
    except Exception as e:
        st.error(f"Error reading CSV: {str(e)}")
        return None


def merge_data(garmin_df, browser_df, time_window_minutes=5):
    """Join Garmin and browser data by timestamp"""
    results = []

    for _, browser_row in browser_df.iterrows():
        visit_time = browser_row['visit_time']
        domain = browser_row['domain']

        time_mask = (
            (garmin_df['timestamp'] >= visit_time - timedelta(minutes=time_window_minutes)) &
            (garmin_df['timestamp'] <= visit_time + timedelta(minutes=time_window_minutes))
        )

        nearby_data = garmin_df[time_mask]

        if not nearby_data.empty:
            avg_hr = nearby_data['heart_rate'].mean()
            avg_stress = nearby_data['stress'].mean()

            results.append({
                'domain': domain,
                'visit_time': visit_time,
                'heart_rate': avg_hr,
                'stress': avg_stress
            })

    return pd.DataFrame(results)


def analyze_stress_by_domain(merged_df):
    """Analyze stress and heart rate by domain"""
    domain_stats = merged_df.groupby('domain').agg({
        'heart_rate': ['mean', 'max', 'count'],
        'stress': ['mean', 'max']
    }).reset_index()

    domain_stats.columns = ['domain', 'avg_hr', 'max_hr', 'visits', 'avg_stress', 'max_stress']
    domain_stats = domain_stats[domain_stats['visits'] >= 3]  # Minimum 3 visits
    domain_stats = domain_stats.sort_values('avg_stress', ascending=False)

    return domain_stats


# --- UI ---

st.title("❤️ Garmin + Browser Stress Analyzer")
st.markdown("Discover which websites raise your stress and heart rate the most!")

# Sidebar
with st.sidebar:
    st.header("🔐 Garmin Login")

    if st.session_state.garmin_client is None:
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Log in"):
            with st.spinner("Logging in..."):
                success, message = login_garmin(email, password)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
    else:
        st.success("✅ Connected to Garmin Connect")
        if st.button("Log out"):
            st.session_state.garmin_client = None
            st.session_state.garmin_data = None
            st.rerun()

    st.divider()

    st.header("📊 Settings")
    days_to_analyze = st.slider("Days to analyze", 1, 30, 7)
    time_window = st.slider("Time window (minutes)", 1, 15, 5)

# Main content
if st.session_state.garmin_client:
    tab1, tab2, tab3 = st.tabs(["📥 Load Data", "📈 Analysis", "🔍 Detail View"])

    with tab1:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Garmin Data")
            if st.button("Load Garmin data", type="primary"):
                with st.spinner(f"Loading data for {days_to_analyze} days..."):
                    garmin_df = get_garmin_data(days_to_analyze)
                    if garmin_df is not None:
                        st.session_state.garmin_data = garmin_df
                        st.success(f"✅ Loaded {len(garmin_df)} records")
                        st.dataframe(garmin_df.head())
                    else:
                        st.error("Failed to load data")

        with col2:
            st.subheader("Browser History")

            load_method = st.radio(
                "How to load history:",
                ["📤 Export from extension (JSON/CSV)", "💾 Direct database read (requires browser to be closed)"],
                help="Export is easier — no need to close your browser!"
            )

            if load_method == "📤 Export from extension (JSON/CSV)":
                st.info("💡 **Recommended**: Export your history using a browser extension")

                with st.expander("📖 How to export your history?", expanded=True):
                    st.markdown("""
                    ### Recommended extensions:

                    **For Chrome / Edge / Brave:**
                    1. Install **"Export Chrome History"** or **"History Trends Unlimited"**
                    2. Open the extension and click "Export"
                    3. Choose JSON or CSV format
                    4. Download the file and upload it below

                    **For Firefox:**
                    1. Install **"Export History"**
                    2. Export as JSON or CSV
                    3. Upload the file below

                    ### Alternative without an extension:
                    - **Chrome**: `chrome://history/` → Ctrl+A → Ctrl+C → paste into a text editor → save as CSV
                    - Format: `url,title,time` on each line
                    """)

                uploaded_file = st.file_uploader(
                    "Upload exported history file",
                    type=['json', 'csv', 'txt'],
                    help="JSON or CSV file exported from a browser extension"
                )

                if uploaded_file:
                    file_type = uploaded_file.name.split('.')[-1].lower()

                    with st.spinner("Processing export..."):
                        try:
                            if file_type == 'json':
                                content = uploaded_file.read().decode('utf-8')
                                browser_df = parse_exported_json(content)
                            else:
                                browser_df = parse_exported_csv(uploaded_file)

                            if browser_df is not None and not browser_df.empty:
                                st.session_state.browser_data = browser_df
                                st.success(f"✅ Loaded {len(browser_df)} records from export!")

                                col_a, col_b, col_c = st.columns(3)
                                with col_a:
                                    st.metric("Total records", len(browser_df))
                                with col_b:
                                    st.metric("Unique domains", browser_df['domain'].nunique())
                                with col_c:
                                    date_range = (browser_df['visit_time'].max() - browser_df['visit_time'].min()).days
                                    st.metric("Date range (days)", date_range)

                                st.dataframe(browser_df.head(10))
                            else:
                                st.error("Failed to load data from export")
                        except Exception as e:
                            st.error(f"Processing error: {str(e)}")
                            st.info("Try a different format or check that the file contains valid data")

            else:  # Direct database read
                st.warning("⚠️ You must **close the browser** you want to analyze before using this method")
                st.info("💡 Tip: Run this app in a different browser than the one you're analyzing")

                browser_paths = find_browser_history_paths()
                available_browsers = {k: v for k, v in browser_paths.items() if v}

                if available_browsers:
                    st.success(f"✅ Found {len(available_browsers)} browser(s)")

                    browser_options = []
                    for browser, paths in available_browsers.items():
                        for i, path in enumerate(paths):
                            label = f"{browser.capitalize()}" + (f" (Profile {i + 1})" if len(paths) > 1 else "")
                            browser_options.append((label, path, browser))

                    selected = st.selectbox(
                        "Select browser",
                        range(len(browser_options)),
                        format_func=lambda i: browser_options[i][0]
                    )

                    if st.button("Load history from database", type="primary"):
                        selected_path = browser_options[selected][1]
                        selected_browser = browser_options[selected][2]

                        with st.spinner("Loading history..."):
                            try:
                                if selected_browser == 'firefox':
                                    browser_df = parse_firefox_history(selected_path)
                                else:
                                    browser_df = parse_chrome_history(selected_path)

                                if browser_df is not None:
                                    st.session_state.browser_data = browser_df
                                    st.success(f"✅ Loaded {len(browser_df)} records from {browser_options[selected][0]}")
                                    st.dataframe(browser_df.head())
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                                st.info("💡 Try closing the browser and retrying, or use the 'Export from extension' method")
                else:
                    st.warning("⚠️ Could not automatically find any browser history")

                with st.expander("📁 Manual database upload"):
                    st.markdown("""
                    **Chrome / Edge / Brave / Opera**: Upload the `History` file  
                    **Firefox**: Upload the `places.sqlite` file
                    """)

                    history_file = st.file_uploader("Upload History / places.sqlite file", type=['sqlite', 'db'])

                    if history_file:
                        with open("temp_upload.db", "wb") as f:
                            f.write(history_file.read())

                        browser_type = st.radio("Browser type", ["Chrome / Edge / Brave", "Firefox"])

                        if st.button("Load uploaded data"):
                            if browser_type == "Firefox":
                                browser_df = parse_firefox_history("temp_upload.db")
                            else:
                                browser_df = parse_chrome_history("temp_upload.db")

                            if browser_df is not None:
                                st.session_state.browser_data = browser_df
                                st.success(f"✅ Loaded {len(browser_df)} records")
                                st.dataframe(browser_df.head())

                            Path("temp_upload.db").unlink()

    with tab2:
        if st.session_state.garmin_data is not None and st.session_state.browser_data is not None:
            st.subheader("🎯 Stress Analysis by Website")

            with st.spinner("Merging data..."):
                merged = merge_data(
                    st.session_state.garmin_data,
                    st.session_state.browser_data,
                    time_window
                )

                if not merged.empty:
                    stats = analyze_stress_by_domain(merged)

                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown("### 🔴 Most Stressful Sites")
                        fig = px.bar(
                            stats.head(10),
                            x='avg_stress',
                            y='domain',
                            orientation='h',
                            color='avg_stress',
                            color_continuous_scale='Reds',
                            labels={'avg_stress': 'Average Stress', 'domain': 'Domain'}
                        )
                        st.plotly_chart(fig, use_container_width=True)

                    with col2:
                        st.markdown("### 💓 Highest Heart Rate Sites")
                        fig = px.bar(
                            stats.sort_values('avg_hr', ascending=False).head(10),
                            x='avg_hr',
                            y='domain',
                            orientation='h',
                            color='avg_hr',
                            color_continuous_scale='Blues',
                            labels={'avg_hr': 'Average HR (bpm)', 'domain': 'Domain'}
                        )
                        st.plotly_chart(fig, use_container_width=True)

                    st.markdown("### 📊 Full Statistics")
                    st.dataframe(stats, use_container_width=True)
                else:
                    st.warning("No matching data found between Garmin and browser history.")
        else:
            st.info("👆 First load both Garmin data and browser history in the 'Load Data' tab")

    with tab3:
        if st.session_state.garmin_data is not None and st.session_state.browser_data is not None:
            st.subheader("🔍 Detailed Timeline")

            merged = merge_data(
                st.session_state.garmin_data,
                st.session_state.browser_data,
                time_window
            )

            if not merged.empty:
                selected_domain = st.selectbox(
                    "Select domain for detail view",
                    merged['domain'].unique()
                )

                domain_data = merged[merged['domain'] == selected_domain].sort_values('visit_time')

                fig = go.Figure()

                fig.add_trace(go.Scatter(
                    x=domain_data['visit_time'],
                    y=domain_data['heart_rate'],
                    name='Heart Rate',
                    mode='lines+markers',
                    yaxis='y1'
                ))

                fig.add_trace(go.Scatter(
                    x=domain_data['visit_time'],
                    y=domain_data['stress'],
                    name='Stress Level',
                    mode='lines+markers',
                    yaxis='y2'
                ))

                fig.update_layout(
                    title=f"Biometrics during visits to: {selected_domain}",
                    xaxis_title="Time",
                    yaxis=dict(title="Heart Rate (bpm)"),
                    yaxis2=dict(title="Stress (0–100)", overlaying='y', side='right'),
                    hovermode='x unified'
                )

                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(domain_data, use_container_width=True)

else:
    st.info("👈 Log in to your Garmin account in the left sidebar to get started.")

    with st.expander("ℹ️ How to use this app"):
        st.markdown("""
        ### Steps:

        1. **Log in to Garmin Connect** using the sidebar
        2. **Load Garmin data** — the app will download your heart rate and stress history
        3. **Load browser history** — two options:

           **🌟 Recommended — Export from extension:**
           - Install a history export extension (e.g. "Export Chrome History")
           - Export as JSON or CSV
           - Upload the file — **no need to close your browser!**

           **💾 Direct database read:**
           - Close the browser you want to analyze
           - Run this app in a different browser
           - The app will auto-detect and load the database

        4. **Explore results** — the app joins the data and shows which sites raise your stress

        ### Recommended export extensions:

        **Chrome / Edge / Brave:**
        - Export Chrome History
        - History Trends Unlimited
        - History Export & Backup

        **Firefox:**
        - Export History
        - Firefox History Export

        ### What the app does:
        - Joins browser visit timestamps with your biometric data
        - Calculates average heart rate and stress during visits to each domain
        - Ranks the most physiologically activating websites

        ### Notes:
        - All data is processed locally in your Streamlit instance
        - The export method is simpler and more reliable
        - Supported formats: JSON, CSV
        - For more accurate results, at least 3 visits per domain are recommended

        ### Troubleshooting:
        - **"Error reading database"** → Use the export from extension method
        - **"Failed to load"** → Check the format of your exported file
        - **"No matches found"** → Try increasing the time window in Settings
        """)