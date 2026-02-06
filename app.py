import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from github import Github
import io
import random

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="Production Scheduling Pro", layout="wide", page_icon="📅")

# --- KẾT NỐI GITHUB ---
try:
    GITHUB_TOKEN = st.secrets["github"]["token"]
    REPO_NAME = st.secrets["github"]["repo_name"]
    FILE_PATH = "jobs_data_v3.csv" # Đổi tên file để tránh lỗi dữ liệu cũ
except:
    st.error("⚠️ Chưa cấu hình Secrets! Hãy kiểm tra lại file .streamlit/secrets.toml")
    st.stop()

# --- SIDEBAR CẤU HÌNH (QUAN TRỌNG) ---
st.sidebar.header("⚙️ Cấu hình Dữ liệu")
st.sidebar.write("Chọn các trường thông tin bạn muốn theo dõi. Nếu bỏ chọn, quy tắc tương ứng sẽ bị ẩn.")

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
        
        # Tạo cột mặc định nếu chưa có
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

# --- LOGIC TẠO RANDOM (LINH HOẠT THEO CẤU HÌNH) ---
def generate_random_jobs(n):
    jobs = []
    setup_types = ['Type A', 'Type B', 'Type C', 'Type D']
    for i in range(1, n + 1):
        pt = random.randint(2, 15) # 2 đến 15 ngày
        dd = pt + random.randint(0, int(n)) # Due date
        
        job = {
            "Job ID": f"J{i}",
            "Processing Time": pt,
            "Due Date": dd,
            "Priority": 1, # Mặc định
            "Setup Type": "A" # Mặc định
        }
        
        if use_priority:
            job["Priority"] = random.randint(1, 10)
        if use_setup:
            job["Setup Type"] = random.choice(setup_types)
            
        jobs.append(job)
    return pd.DataFrame(jobs)

# --- LOGIC TÍNH TOÁN ---
def calculate_schedule(df, rule_code):
    data = df.copy()
    
    # Ép kiểu số
    data['Processing Time'] = pd.to_numeric(data['Processing Time']).fillna(0)
    data['Due Date'] = pd.to_numeric(data['Due Date']).fillna(0)
    if use_priority:
        data['Priority'] = pd.to_numeric(data['Priority']).fillna(1)
    
    # --- CÁC QUY TẮC ---
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
    elif rule_code == "CUSTPR" and use_priority: # Chỉ chạy nếu bật Priority
        data = data.sort_values(by="Priority", ascending=False)
    elif rule_code == "SETUP" and use_setup: # Chỉ chạy nếu bật Setup
        data = data.sort_values(by="Setup Type")

    # --- TÍNH TOÁN NGÀY ---
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
st.title("📅 Quản lý Điều độ Sản xuất (Theo Ngày)")

if 'jobs' not in st.session_state:
    with st.spinner('Đang tải dữ liệu...'):
        st.session_state.jobs = get_data_from_github()

df_jobs = st.session_state.jobs

# --- KHU VỰC 1: INPUT ---
st.markdown("### 1. Dữ liệu đầu vào")
tab_manual, tab_random = st.tabs(["✍️ Nhập Thủ Công", "🎲 Tạo Ngẫu Nhiên"])

with tab_manual:
    with st.container(border=True):
        # Tạo số cột động dựa trên cấu hình
        cols_count = 3 + (1 if use_priority else 0) + (1 if use_setup else 0) + 1 # +1 cho nút bấm
        cols = st.columns(cols_count)
        
        idx = 0
        with cols[idx]: new_id = st.text_input("Job ID", placeholder="J1"); idx+=1
        with cols[idx]: new_pt = st.number_input("TG (Ngày)", min_value=1, value=5); idx+=1
        with cols[idx]: new_dd = st.number_input("Hạn chót (Ngày)", min_value=1, value=10); idx+=1
        
        new_prio = 1
        if use_priority:
            with cols[idx]: new_prio = st.number_input("Ưu tiên (1-10)", 1, 10, 5); idx+=1
            
        new_setup = "A"
        if use_setup:
            with cols[idx]: new_setup = st.selectbox("Setup", ["A", "B", "C", "D"]); idx+=1
            
        with cols[idx]:
            st.write("")
            st.write("")
            if st.button("➕ Thêm", use_container_width=True):
                if new_id and new_id not in df_jobs['Job ID'].values:
                    new_row = {
                        'Job ID': str(new_id), 
                        'Processing Time': int(new_pt), 
                        'Due Date': int(new_dd),
                        'Priority': int(new_prio),
                        'Setup Type': new_setup
                    }
                    updated_df = pd.concat([df_jobs, pd.DataFrame([new_row])], ignore_index=True)
                    if save_data_to_github(updated_df, f"Add {new_id}"):
                        st.session_state.jobs = updated_df
                        st.success(f"Đã thêm {new_id}")
                        st.rerun()
                else:
                    st.warning("Job ID trùng!")

with tab_random:
    c_r1, c_r2 = st.columns([3, 1])
    with c_r1: num_jobs = st.slider("Số lượng Job:", 5, 100, 10)
    with c_r2: 
        st.write("")
        if st.button("🎲 Tạo mới", type="primary", use_container_width=True):
            random_df = generate_random_jobs(num_jobs)
            if save_data_to_github(random_df, "Gen Random"):
                st.session_state.jobs = random_df
                st.rerun()

# --- KHU VỰC 2: BẢNG DỮ LIỆU ---
st.markdown("### 2. Danh sách công việc")

# Cấu hình cột hiển thị động
col_config = {
    "Job ID": st.column_config.TextColumn("Job ID", required=True),
    "Processing Time": st.column_config.NumberColumn("TG (Ngày)", min_value=0),
    "Due Date": st.column_config.NumberColumn("Hạn chót (Ngày)", min_value=0),
}
if use_priority:
    col_config["Priority"] = st.column_config.NumberColumn("Độ ưu tiên", min_value=1, max_value=10)
if use_setup:
    col_config["Setup Type"] = st.column_config.SelectboxColumn("Loại Setup", options=["Type A", "Type B", "Type C", "Type D"])

# Ẩn cột nếu không dùng
display_cols = ['Job ID', 'Processing Time', 'Due Date']
if use_priority: display_cols.append('Priority')
if use_setup: display_cols.append('Setup Type')

edited_df = st.data_editor(
    st.session_state.jobs[display_cols], # Chỉ hiện cột được chọn
    use_container_width=True,
    num_rows="dynamic",
    key="editor",
    column_config=col_config
)

if st.button("💾 Lưu thay đổi bảng"):
    # Hợp nhất dữ liệu edit vào dữ liệu gốc (để giữ lại các cột ẩn nếu có)
    final_df = st.session_state.jobs.copy()
    
    # Cập nhật các dòng hiện có
    # (Đơn giản hóa: thay thế toàn bộ bằng edited_df và fill cột thiếu bằng default)
    edited_df['Processing Time'] = pd.to_numeric(edited_df['Processing Time']).fillna(0).astype(int)
    edited_df['Due Date'] = pd.to_numeric(edited_df['Due Date']).fillna(0).astype(int)
    
    if 'Priority' not in edited_df.columns: edited_df['Priority'] = 1
    if 'Setup Type' not in edited_df.columns: edited_df['Setup Type'] = 'A'
        
    if save_data_to_github(edited_df, "Update table"):
        st.session_state.jobs = edited_df
        st.success("Đã lưu!")
        st.rerun()

# --- KHU VỰC 3: KẾT QUẢ & BIỂU ĐỒ ---
if not edited_df.empty:
    st.divider()
    
    # Lọc danh sách quy tắc dựa trên cấu hình
    rule_map = {
        "SPT - Ngắn nhất làm trước": "SPT",
        "LPT - Dài nhất làm trước": "LPT",
        "FCFS - Đến trước làm trước": "FCFS",
        "DDATE - Hạn chót sớm nhất": "DDATE",
        "SLACK - Slack nhỏ nhất": "SLACK",
        "CR - Tỷ số tới hạn": "CR"
    }
    
    if use_priority:
        rule_map["CUSTPR - Ưu tiên khách hàng"] = "CUSTPR"
    if use_setup:
        rule_map["SETUP - Theo nhóm máy"] = "SETUP"
    
    # --- PHẦN SO SÁNH (BENCHMARK) ---
    st.header("📊 So sánh Hiệu quả (Benchmark)")
    
    # Tính toán cho tất cả quy tắc khả dụng
    comp_data = []
    for name, code in rule_map.items():
        res = calculate_schedule(edited_df, code)
        comp_data.append({
            "Quy tắc": code,
            "Tổng Trễ (Ngày)": res['Lateness'].sum(),
            "Hoàn thành (Makespan)": res['Finish'].max(),
            "TB Lưu kho (Flow Time)": round(res['Finish'].mean(), 2)
        })
    
    df_comp = pd.DataFrame(comp_data)
    
    # Vẽ biểu đồ so sánh (3 Cột)
    fig_bench = px.bar(
        df_comp, 
        x="Quy tắc", 
        y=["Tổng Trễ (Ngày)", "Hoàn thành (Makespan)", "TB Lưu kho (Flow Time)"],
        barmode='group',
        title="Biểu đồ so sánh các chỉ số (Thấp hơn là Tốt hơn)",
        labels={"value": "Số ngày", "variable": "Chỉ số"}
    )
    st.plotly_chart(fig_bench, use_container_width=True)

    # --- PHẦN CHI TIẾT LỊCH TRÌNH ---
    st.divider()
    st.subheader("🔎 Chi tiết & Gantt Chart")
    
    selected_rule_name = st.selectbox("Chọn quy tắc để xem:", list(rule_map.keys()))
    selected_rule_code = rule_map[selected_rule_name]
    
    result_df = calculate_schedule(edited_df, selected_rule_code)
    
    # Metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("Hoàn thành sau", f"{result_df['Finish'].max()} ngày")
    m2.metric("Tổng ngày trễ", f"{result_df['Lateness'].sum()} ngày", delta_color="inverse")
    m3.metric("Số Job trễ", f"{(result_df['Lateness'] > 0).sum()} job")

    # Gantt Chart (ĐƠN VỊ NGÀY)
    # Dùng ngày giả định bắt đầu, cộng thêm số NGÀY (unit='D')
    base_date = pd.Timestamp("2024-01-01")
    gantt_data = result_df.copy()
    gantt_data['Start_Date'] = base_date + pd.to_timedelta(gantt_data['Start'], unit='D')
    gantt_data['Finish_Date'] = base_date + pd.to_timedelta(gantt_data['Finish'], unit='D')
    
    # Màu sắc
    color_col = "Setup Type" if selected_rule_code == "SETUP" else "Lateness"
    
    fig = px.timeline(
        gantt_data, 
        x_start="Start_Date", x_end="Finish_Date", 
        y="Job ID", color=color_col,
        title=f"Lịch trình sản xuất ({selected_rule_name})", 
        text="Job ID",
        height=400 + (len(gantt_data) * 20) # Tự động chỉnh chiều cao
    )
    
    # Chỉnh trục X hiển thị theo ngày
    fig.update_xaxes(
        tickformat="%d/%m", # Định dạng ngày tháng
        dtick="D1" # Mỗi vạch là 1 ngày
    )
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)
    
    with st.expander("Xem bảng dữ liệu chi tiết"):
        st.dataframe(result_df)
