import streamlit as st
import pandas as pd
import plotly.express as px
from github import Github
import io
import random

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="Production Scheduling Pro", layout="wide", page_icon="📊")

# --- KẾT NỐI GITHUB ---
try:
    GITHUB_TOKEN = st.secrets["github"]["token"]
    REPO_NAME = st.secrets["github"]["repo_name"]
    FILE_PATH = "jobs_data_v3.csv"
except:
    st.error("⚠️ Chưa cấu hình Secrets! Hãy kiểm tra lại file .streamlit/secrets.toml")
    st.stop()

# --- SIDEBAR CẤU HÌNH ---
st.sidebar.header("⚙️ Cấu hình Dữ liệu")
st.sidebar.write("Chọn các trường thông tin bạn muốn theo dõi:")
use_priority = st.sidebar.checkbox("Sử dụng Độ ưu tiên (Priority)", value=True)
use_setup = st.sidebar.checkbox("Sử dụng Loại Setup (Nhóm máy)", value=True)

# --- HÀM XỬ LÝ DỮ LIỆU ---
def get_data_from_github():
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        contents = repo.get_contents(FILE_PATH)
        decoded = contents.decoded_content.decode("utf-8")
        if not decoded: return create_empty_df()
        
        df = pd.read_csv(io.StringIO(decoded))
        
        # Ép kiểu dữ liệu
        df['Job ID'] = df['Job ID'].astype(str)
        df['Processing Time'] = pd.to_numeric(df['Processing Time'], errors='coerce').fillna(0).astype(int)
        df['Due Date'] = pd.to_numeric(df['Due Date'], errors='coerce').fillna(0).astype(int)
        
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

# --- LOGIC TẠO RANDOM ---
def generate_random_jobs(n):
    jobs = []
    setup_types = ['Type A', 'Type B', 'Type C', 'Type D']
    for i in range(1, n + 1):
        pt = random.randint(2, 15)
        dd = pt + random.randint(0, int(n))
        
        job = {
            "Job ID": f"J{i}",
            "Processing Time": pt,
            "Due Date": dd,
            "Priority": 1,
            "Setup Type": "A"
        }
        
        if use_priority: job["Priority"] = random.randint(1, 10)
        if use_setup: job["Setup Type"] = random.choice(setup_types)
            
        jobs.append(job)
    return pd.DataFrame(jobs)

# --- LOGIC TÍNH TOÁN ---
def calculate_schedule(df, rule_code):
    data = df.copy()
    
    data['Processing Time'] = pd.to_numeric(data['Processing Time']).fillna(0)
    data['Due Date'] = pd.to_numeric(data['Due Date']).fillna(0)
    if use_priority: data['Priority'] = pd.to_numeric(data['Priority']).fillna(1)
    
    # SẮP XẾP
    if rule_code == "SPT": data = data.sort_values(by="Processing Time")
    elif rule_code == "LPT": data = data.sort_values(by="Processing Time", ascending=False)
    elif rule_code == "DDATE": data = data.sort_values(by="Due Date")
    elif rule_code == "LCFS": data = data.iloc[::-1]
    elif rule_code == "SLACK": 
        data['Slack'] = data['Due Date'] - data['Processing Time']
        data = data.sort_values(by="Slack")
    elif rule_code == "CR": 
        data['CR_Value'] = data['Due Date'] / data['Processing Time'].replace(0, 0.1)
        data = data.sort_values(by="CR_Value")
    elif rule_code == "CUSTPR" and use_priority:
        data = data.sort_values(by="Priority", ascending=False)
    elif rule_code == "SETUP" and use_setup:
        data = data.sort_values(by="Setup Type")

    # TÍNH TOÁN (Số học)
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
st.title("📅 Quản lý Điều độ (Trục Số Ngày)")

if 'jobs' not in st.session_state:
    with st.spinner('Đang tải dữ liệu...'):
        st.session_state.jobs = get_data_from_github()

df_jobs = st.session_state.jobs

# --- KHU VỰC 1: INPUT ---
st.markdown("### 1. Dữ liệu đầu vào")
tab_manual, tab_random = st.tabs(["✍️ Nhập Thủ Công", "🎲 Tạo Ngẫu Nhiên"])

with tab_manual:
    with st.container(border=True):
        cols_count = 3 + (1 if use_priority else 0) + (1 if use_setup else 0) + 1
        cols = st.columns(cols_count)
        
        idx = 0
        with cols[idx]: new_id = st.text_input("Job ID", placeholder="J1"); idx+=1
        with cols[idx]: new_pt = st.number_input("TG (Ngày)", min_value=1, value=5); idx+=1
        with cols[idx]: new_dd = st.number_input("Hạn chót (Ngày)", min_value=1, value=10); idx+=1
        
        new_prio = 1
        if use_priority:
            with cols[idx]: new_prio = st.number_input("Ưu tiên", 1, 10, 5); idx+=1
        new_setup = "A"
        if use_setup:
            with cols[idx]: new_setup = st.selectbox("Setup", ["A", "B", "C", "D"]); idx+=1
            
        with cols[idx]:
            st.write("")
            st.write("")
            if st.button("➕ Thêm", use_container_width=True):
                if new_id and new_id not in df_jobs['Job ID'].values:
                    new_row = {'Job ID': str(new_id), 'Processing Time': int(new_pt), 'Due Date': int(new_dd), 'Priority': int(new_prio), 'Setup Type': new_setup}
                    updated_df = pd.concat([df_jobs, pd.DataFrame([new_row])], ignore_index=True)
                    if save_data_to_github(updated_df, f"Add {new_id}"):
                        st.session_state.jobs = updated_df
                        st.success(f"Đã thêm {new_id}")
                        st.rerun()
                else:
                    st.warning("Trùng ID!")

with tab_random:
    c1, c2 = st.columns([3, 1])
    with c1: num_jobs = st.slider("Số lượng Job:", 5, 100, 10)
    with c2: 
        st.write("")
        if st.button("🎲 Tạo Mới", type="primary", use_container_width=True):
            random_df = generate_random_jobs(num_jobs)
            if save_data_to_github(random_df, "Gen Random"):
                st.session_state.jobs = random_df
                st.rerun()

# --- KHU VỰC 2: EDIT TABLE ---
st.markdown("### 2. Danh sách công việc")
col_config = {
    "Job ID": st.column_config.TextColumn("Job ID", required=True),
    "Processing Time": st.column_config.NumberColumn("TG (Ngày)", min_value=0),
    "Due Date": st.column_config.NumberColumn("Hạn chót (Ngày)", min_value=0),
}
if use_priority: col_config["Priority"] = st.column_config.NumberColumn("Độ ưu tiên")
if use_setup: col_config["Setup Type"] = st.column_config.SelectboxColumn("Loại Setup", options=["Type A", "Type B", "Type C", "Type D"])

display_cols = ['Job ID', 'Processing Time', 'Due Date']
if use_priority: display_cols.append('Priority')
if use_setup: display_cols.append('Setup Type')

edited_df = st.data_editor(st.session_state.jobs[display_cols], use_container_width=True, num_rows="dynamic", key="editor", column_config=col_config)

if st.button("💾 Lưu thay đổi bảng"):
    final_df = st.session_state.jobs.copy()
    edited_df['Processing Time'] = pd.to_numeric(edited_df['Processing Time']).fillna(0).astype(int)
    edited_df['Due Date'] = pd.to_numeric(edited_df['Due Date']).fillna(0).astype(int)
    if 'Priority' not in edited_df.columns: edited_df['Priority'] = 1
    if 'Setup Type' not in edited_df.columns: edited_df['Setup Type'] = 'A'
    
    if save_data_to_github(edited_df, "Update table"):
        st.session_state.jobs = edited_df
        st.success("Đã lưu!")
        st.rerun()

# --- KHU VỰC 3: KẾT QUẢ & BIỂU ĐỒ SỐ ---
if not edited_df.empty:
    st.divider()
    
    rule_map = {
        "SPT - Ngắn nhất làm trước": "SPT",
        "LPT - Dài nhất làm trước": "LPT",
        "FCFS - Đến trước làm trước": "FCFS",
        "DDATE - Hạn chót sớm nhất": "DDATE",
        "SLACK - Slack nhỏ nhất": "SLACK",
        "CR - Tỷ số tới hạn": "CR"
    }
    if use_priority: rule_map["CUSTPR - Ưu tiên khách hàng"] = "CUSTPR"
    if use_setup: rule_map["SETUP - Theo nhóm máy"] = "SETUP"
    
    # --- BENCHMARK ---
    st.header("📊 So sánh Hiệu quả")
    comp_data = []
    for name, code in rule_map.items():
        res = calculate_schedule(edited_df, code)
        comp_data.append({"Quy tắc": code, "Tổng Trễ": res['Lateness'].sum(), "Hoàn thành": res['Finish'].max(), "TB Lưu kho": round(res['Finish'].mean(), 2)})
    
    st.plotly_chart(px.bar(pd.DataFrame(comp_data), x="Quy tắc", y=["Tổng Trễ", "Hoàn thành", "TB Lưu kho"], barmode='group', title="So sánh chỉ số (Thấp hơn là Tốt hơn)"), use_container_width=True)

    # --- GANTT CHART (TRỤC SỐ) ---
    st.divider()
    st.subheader("🔎 Chi tiết & Gantt Chart (Theo số ngày)")
    
    selected_rule_name = st.selectbox("Chọn quy tắc:", list(rule_map.keys()))
    selected_rule_code = rule_map[selected_rule_name]
    
    result_df = calculate_schedule(edited_df, selected_rule_code)
    
    # Metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("Hoàn thành (Makespan)", f"{result_df['Finish'].max()} ngày")
    m2.metric("Tổng trễ", f"{result_df['Lateness'].sum()} ngày", delta_color="inverse")
    m3.metric("Số Job trễ", f"{(result_df['Lateness'] > 0).sum()} job")

    # --- [CHỈNH SỬA QUAN TRỌNG]: Dùng px.bar với base để vẽ Gantt trục số ---
    # color_col xác định màu theo Setup hoặc theo Lateness
    color_col = "Setup Type" if selected_rule_code == "SETUP" else "Lateness"
    
    fig = px.bar(
        result_df,
        base="Start",         # Điểm bắt đầu của thanh (Số ngày)
        x="Processing Time",  # Độ dài của thanh (Số ngày)
        y="Job ID",           # Trục tung là tên Job
        orientation='h',      # Nằm ngang
        color=color_col,
        text="Processing Time", # Hiển thị số ngày trên thanh
        title=f"Lịch trình sản xuất - {selected_rule_name}",
        labels={"Processing Time": "Thời gian thực hiện (Ngày)", "Start": "Ngày bắt đầu", "Job ID": "Công việc"},
        color_continuous_scale="RdYlGn_r" if color_col == "Lateness" else None # Màu đỏ-xanh cho độ trễ
    )
    
    # Tinh chỉnh giao diện biểu đồ
    fig.update_layout(
        xaxis_title="Thời gian (Ngày thứ 0, 1, 2...)",
        yaxis=dict(autorange="reversed"), # Đảo ngược để Job đầu tiên nằm trên cùng
        height=400 + (len(result_df) * 20) # Chiều cao tự động
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    with st.expander("Xem bảng dữ liệu chi tiết"):
        st.dataframe(result_df)
