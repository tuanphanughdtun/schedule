import streamlit as st
import pandas as pd
import plotly.express as px
from github import Github
import io
import random

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="Production Scheduling Ultimate", layout="wide", page_icon="🏭")

# --- KẾT NỐI GITHUB ---
try:
    GITHUB_TOKEN = st.secrets["github"]["token"]
    REPO_NAME = st.secrets["github"]["repo_name"]
    FILE_PATH = "jobs_data_v2.csv" # Đổi tên file để tạo dữ liệu mới có cột Priority/Setup
except:
    st.error("⚠️ Chưa cấu hình Secrets! Hãy kiểm tra lại file .streamlit/secrets.toml")
    st.stop()

def get_data_from_github():
    """Lấy dữ liệu và làm sạch, đảm bảo đủ cột"""
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        contents = repo.get_contents(FILE_PATH)
        decoded = contents.decoded_content.decode("utf-8")
        if not decoded:
            return create_empty_df()
        
        df = pd.read_csv(io.StringIO(decoded))
        
        # Ép kiểu dữ liệu an toàn
        df['Job ID'] = df['Job ID'].astype(str)
        df['Processing Time'] = pd.to_numeric(df['Processing Time'], errors='coerce').fillna(0).astype(int)
        df['Due Date'] = pd.to_numeric(df['Due Date'], errors='coerce').fillna(0).astype(int)
        
        # Đảm bảo có cột Priority và Setup (cho quy tắc mới)
        if 'Priority' not in df.columns: df['Priority'] = 1
        if 'Setup Type' not in df.columns: df['Setup Type'] = 'A'
            
        return df
    except:
        return create_empty_df()

def create_empty_df():
    return pd.DataFrame(columns=['Job ID', 'Processing Time', 'Due Date', 'Priority', 'Setup Type'])

def save_data_to_github(df, message):
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        csv_content = df.to_csv(index=False)
        try:
            contents = repo.get_contents(FILE_PATH)
            repo.update_file(contents.path, message, csv_content, contents.sha)
        except:
            repo.create_file(FILE_PATH, message, csv_content)
        return True
    except Exception as e:
        st.error(f"Lỗi lưu GitHub: {e}")
        return False

# --- LOGIC TẠO DỮ LIỆU NGẪU NHIÊN ---
def generate_random_jobs(n):
    jobs = []
    setup_types = ['Type A', 'Type B', 'Type C', 'Type D']
    for i in range(1, n + 1):
        pt = random.randint(5, 30)
        slack = random.randint(0, int(n * 2)) 
        dd = pt + slack 
        jobs.append({
            "Job ID": f"J{i}",
            "Processing Time": pt,
            "Due Date": dd,
            "Priority": random.randint(1, 10), # 1-10 (10 là quan trọng nhất)
            "Setup Type": random.choice(setup_types) # Loại setup ngẫu nhiên
        })
    return pd.DataFrame(jobs)

# --- LOGIC TÍNH TOÁN (ĐẦY ĐỦ QUY TẮC) ---
def calculate_schedule(df, rule_code):
    data = df.copy()
    
    # Ép kiểu số
    data['Processing Time'] = pd.to_numeric(data['Processing Time']).fillna(0)
    data['Due Date'] = pd.to_numeric(data['Due Date']).fillna(0)
    data['Priority'] = pd.to_numeric(data['Priority']).fillna(1)
    
    # --- CÁC QUY TẮC SẮP XẾP ---
    if rule_code == "SPT": # Shortest Processing Time
        data = data.sort_values(by="Processing Time")
        
    elif rule_code == "LPT": # Longest Processing Time
        data = data.sort_values(by="Processing Time", ascending=False)
        
    elif rule_code == "DDATE": # Earliest Due Date (EDD)
        data = data.sort_values(by="Due Date")
        
    elif rule_code == "FCFS": # First Come First Served
        pass # Giữ nguyên thứ tự nhập liệu
        
    elif rule_code == "LCFS": # Last Come First Served
        data = data.iloc[::-1] # Đảo ngược danh sách
        
    elif rule_code == "SLACK": # Smallest Slack (STR)
        data['Slack'] = data['Due Date'] - data['Processing Time']
        data = data.sort_values(by="Slack")
        
    elif rule_code == "CUSTPR": # Highest Customer Priority
        # Sắp xếp theo độ ưu tiên giảm dần (10 làm trước, 1 làm sau)
        data = data.sort_values(by="Priority", ascending=False)
        
    elif rule_code == "SETUP": # Similar Required Setups
        # Gom nhóm các Job có cùng Setup Type lại gần nhau
        data = data.sort_values(by="Setup Type")
        
    elif rule_code == "CR": # Critical Ratio
        # CR = Due Date / Processing Time (Tại thời điểm t=0)
        # Tránh chia cho 0
        data['CR_Value'] = data['Due Date'] / data['Processing Time'].replace(0, 0.1)
        data = data.sort_values(by="CR_Value")

    # --- TÍNH TOÁN THỜI GIAN ---
    current_time = 0
    start_times, finish_times, lateness = [], [], []
    
    for _, row in data.iterrows():
        start = current_time
        finish = start + row['Processing Time']
        late = max(0, finish - row['Due Date'])
        
        start_times.append(start)
        finish_times.append(finish)
        lateness.append(late)
        current_time = finish

    data['Start'] = start_times
    data['Finish'] = finish_times
    data['Lateness'] = lateness
    return data

# --- GIAO DIỆN CHÍNH ---
st.title("🏭 Web Điều độ Công việc (Full Rules)")

if 'jobs' not in st.session_state:
    with st.spinner('Đang đồng bộ dữ liệu...'):
        st.session_state.jobs = get_data_from_github()

df_jobs = st.session_state.jobs

# --- KHU VỰC 1: INPUT DỮ LIỆU ---
st.markdown("### 1. Dữ liệu đầu vào")
tab_manual, tab_random = st.tabs(["✍️ Nhập Thủ Công", "🎲 Tạo Ngẫu Nhiên"])

with tab_manual:
    with st.container(border=True):
        # 5 Cột nhập liệu
        c1, c2, c3, c4, c5, c6 = st.columns([2, 2, 2, 2, 2, 2])
        with c1: new_id = st.text_input("Job ID", placeholder="VD: J1")
        with c2: new_pt = st.number_input("TG Xử lý", min_value=1, value=10)
        with c3: new_dd = st.number_input("Hạn chót", min_value=1, value=20)
        with c4: new_prio = st.number_input("Ưu tiên (1-10)", min_value=1, max_value=10, value=5)
        with c5: new_setup = st.selectbox("Loại Setup", ["Type A", "Type B", "Type C", "Type D"])
        with c6:
            st.write("")
            st.write("")
            if st.button("➕ Thêm Job", use_container_width=True):
                if new_id and new_id not in df_jobs['Job ID'].values:
                    new_row = pd.DataFrame({
                        'Job ID': [str(new_id)], 
                        'Processing Time': [int(new_pt)], 
                        'Due Date': [int(new_dd)],
                        'Priority': [int(new_prio)],
                        'Setup Type': [new_setup]
                    })
                    updated_df = pd.concat([df_jobs, new_row], ignore_index=True)
                    if save_data_to_github(updated_df, f"Add {new_id}"):
                        st.session_state.jobs = updated_df
                        st.success(f"Đã thêm {new_id}")
                        st.rerun()
                else:
                    st.warning("Job ID trùng hoặc trống!")

with tab_random:
    with st.container(border=True):
        c_r1, c_r2 = st.columns([3, 1])
        with c_r1: num_jobs = st.slider("Số lượng Job muốn tạo:", 5, 200, 10)
        with c_r2: 
            st.write("")
            if st.button("🎲 Tạo mới & Lưu", type="primary", use_container_width=True):
                random_df = generate_random_jobs(num_jobs)
                if save_data_to_github(random_df, "Generate Random Data"):
                    st.session_state.jobs = random_df
                    st.success("Đã tạo dữ liệu mới!")
                    st.rerun()

# --- KHU VỰC 2: HIỂN THỊ VÀ SỬA ---
st.markdown("### 2. Danh sách công việc")
edited_df = st.data_editor(
    st.session_state.jobs,
    use_container_width=True,
    num_rows="dynamic",
    key="editor",
    column_config={
        "Job ID": st.column_config.TextColumn("Job ID", required=True),
        "Processing Time": st.column_config.NumberColumn("TG Xử lý (PT)", min_value=0, format="%d"),
        "Due Date": st.column_config.NumberColumn("Hạn chót (DD)", min_value=0, format="%d"),
        "Priority": st.column_config.NumberColumn("Độ ưu tiên (1-10)", min_value=1, max_value=10),
        "Setup Type": st.column_config.SelectboxColumn("Loại Setup", options=["Type A", "Type B", "Type C", "Type D"]),
    }
)

if not edited_df.equals(st.session_state.jobs):
    if st.button("💾 Lưu thay đổi bảng"):
        edited_df['Processing Time'] = pd.to_numeric(edited_df['Processing Time']).fillna(0).astype(int)
        edited_df['Due Date'] = pd.to_numeric(edited_df['Due Date']).fillna(0).astype(int)
        edited_df['Priority'] = pd.to_numeric(edited_df['Priority']).fillna(1).astype(int)
        if save_data_to_github(edited_df, "Table update"):
            st.session_state.jobs = edited_df
            st.success("Đã lưu!")
            st.rerun()

# --- KHU VỰC 3: KẾT QUẢ & SO SÁNH ---
if not edited_df.empty:
    st.divider()
    
    # Map tên quy tắc
    rule_map = {
        "SPT - Shortest Processing Time": "SPT",
        "LPT - Longest Processing Time": "LPT",
        "FCFS - First Come First Served": "FCFS",
        "LCFS - Last Come First Served": "LCFS",
        "DDATE - Earliest Due Date": "DDATE",
        "SLACK - Smallest Slack": "SLACK",
        "CUSTPR - Highest Customer Priority": "CUSTPR",
        "SETUP - Similar Required Setups": "SETUP",
        "CR - Smallest Critical Ratio": "CR"
    }
    
    col_rule, _ = st.columns([1, 1])
    with col_rule:
        selected_rule_name = st.selectbox("🎯 Chọn quy tắc điều độ:", list(rule_map.keys()))
    
    selected_rule_code = rule_map[selected_rule_name]
    result_df = calculate_schedule(edited_df, selected_rule_code)
    
    # Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Makespan", f"{result_df['Finish'].max()}")
    m2.metric("Mean Flow Time", f"{result_df['Finish'].mean():.2f}")
    m3.metric("Total Tardiness", f"{result_df['Lateness'].sum()}")
    m4.metric("Job bị trễ", f"{(result_df['Lateness'] > 0).sum()}")

    # Gantt Chart
    base_date = pd.Timestamp("2024-01-01 08:00")
    gantt_data = result_df.copy()
    gantt_data['Start_Date'] = base_date + pd.to_timedelta(gantt_data['Start'], unit='m')
    gantt_data['Finish_Date'] = base_date + pd.to_timedelta(gantt_data['Finish'], unit='m')
    
    # Tạo màu sắc theo Loại Setup nếu chọn quy tắc SETUP, ngược lại theo độ trễ
    color_col = "Setup Type" if selected_rule_code == "SETUP" else "Lateness"
    color_scale = None if selected_rule_code == "SETUP" else "RdYlGn_r"
    
    fig = px.timeline(
        gantt_data, x_start="Start_Date", x_end="Finish_Date", 
        y="Job ID", color=color_col,
        title=f"Biểu đồ Gantt ({selected_rule_name})", 
        color_continuous_scale=color_scale, text="Job ID"
    )
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)

    # BẢNG SO SÁNH
    st.divider()
    with st.expander("📊 Xem bảng so sánh hiệu quả các quy tắc (Benchmark)", expanded=False):
        comp_data = []
        for name, code in rule_map.items():
            res = calculate_schedule(edited_df, code)
            comp_data.append({
                "Quy Tắc": code,
                "Tổng Trễ (Tardiness)": res['Lateness'].sum(),
                "TB Lưu Kho (Flow Time)": round(res['Finish'].mean(), 2),
                "Job Trễ": (res['Lateness'] > 0).sum()
            })
        
        st.dataframe(pd.DataFrame(comp_data).style.highlight_min(axis=0, color='#90EE90', subset=["Tổng Trễ (Tardiness)", "TB Lưu Kho (Flow Time)"]), use_container_width=True)
