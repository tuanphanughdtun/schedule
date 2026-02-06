import streamlit as st
import pandas as pd
import plotly.express as px
from github import Github
import io
import random

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="Dynamic Scheduling System", layout="wide", page_icon="⏱️")

# --- KẾT NỐI GITHUB ---
try:
    GITHUB_TOKEN = st.secrets["github"]["token"]
    REPO_NAME = st.secrets["github"]["repo_name"]
    FILE_PATH = "jobs_data_v4.csv" # Đổi tên file sang v4 vì cấu trúc dữ liệu thay đổi
except:
    st.error("⚠️ Chưa cấu hình Secrets! Hãy kiểm tra lại file .streamlit/secrets.toml")
    st.stop()

# --- SIDEBAR CẤU HÌNH ---
st.sidebar.header("⚙️ Cấu hình Dữ liệu")
use_release = st.sidebar.checkbox("Sử dụng Release Time (Thời điểm đến)", value=True)
use_priority = st.sidebar.checkbox("Sử dụng Độ ưu tiên (Priority)", value=False)
use_setup = st.sidebar.checkbox("Sử dụng Loại Setup (Nhóm máy)", value=False)

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
        
        # Tạo cột mặc định nếu thiếu
        if 'Release Time' not in df.columns: df['Release Time'] = 0
        if 'Priority' not in df.columns: df['Priority'] = 1
        if 'Setup Type' not in df.columns: df['Setup Type'] = 'A'
            
        return df
    except:
        return create_empty_df()

def create_empty_df():
    return pd.DataFrame(columns=['Job ID', 'Release Time', 'Processing Time', 'Due Date', 'Priority', 'Setup Type'])

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
        pt = random.randint(2, 10)
        # Release time: rải rác từ 0 đến n
        rel = random.randint(0, n) if use_release else 0
        # Due date: phải lớn hơn Release + PT một chút
        dd = rel + pt + random.randint(2, int(n))
        
        job = {
            "Job ID": f"J{i}",
            "Release Time": rel,
            "Processing Time": pt,
            "Due Date": dd,
            "Priority": 1,
            "Setup Type": "A"
        }
        
        if use_priority: job["Priority"] = random.randint(1, 10)
        if use_setup: job["Setup Type"] = random.choice(setup_types)
            
        jobs.append(job)
    return pd.DataFrame(jobs)

# --- LOGIC TÍNH TOÁN: MÔ PHỎNG (SIMULATION) ---
def calculate_schedule(df, rule_code):
    # Sao chép dữ liệu để xử lý
    remaining_jobs = df.copy()
    
    # Ép kiểu số
    remaining_jobs['Release Time'] = pd.to_numeric(remaining_jobs['Release Time']).fillna(0) if use_release else 0
    remaining_jobs['Processing Time'] = pd.to_numeric(remaining_jobs['Processing Time']).fillna(0)
    remaining_jobs['Due Date'] = pd.to_numeric(remaining_jobs['Due Date']).fillna(0)
    if use_priority: remaining_jobs['Priority'] = pd.to_numeric(remaining_jobs['Priority']).fillna(1)
    
    current_time = 0
    scheduled_jobs = []
    
    # Vòng lặp mô phỏng: Chạy đến khi không còn job nào
    while not remaining_jobs.empty:
        # 1. Tìm các job đã "đến" (Available) tại thời điểm hiện tại
        available_mask = remaining_jobs['Release Time'] <= current_time
        available_jobs = remaining_jobs[available_mask]
        
        # 2. Nếu không có job nào sẵn sàng -> Máy phải chờ (Idle)
        if available_jobs.empty:
            # Nhảy thời gian đến thời điểm job tiếp theo release
            next_arrival = remaining_jobs['Release Time'].min()
            current_time = next_arrival
            continue # Quay lại đầu vòng lặp
            
        # 3. Chọn Job tốt nhất trong số các Job đang chờ theo RULE
        best_job_idx = None
        
        if rule_code == "SPT": # Ngắn làm trước
            best_job_idx = available_jobs['Processing Time'].idxmin()
            
        elif rule_code == "LPT": # Dài làm trước
            best_job_idx = available_jobs['Processing Time'].idxmax()
            
        elif rule_code == "DDATE": # Hạn chót sớm nhất (EDD)
            best_job_idx = available_jobs['Due Date'].idxmin()
            
        elif rule_code == "FCFS": # Đến sớm làm trước (theo Release Time)
            best_job_idx = available_jobs['Release Time'].idxmin()
            
        elif rule_code == "SLACK": # Slack nhỏ nhất
            # Slack = DueDate - CurrentTime - ProcessingTime
            # (Lưu ý: Slack tính tại thời điểm hiện tại t)
            slacks = available_jobs['Due Date'] - current_time - available_jobs['Processing Time']
            best_job_idx = slacks.idxmin()
            
        elif rule_code == "CR": # Critical Ratio
            # CR = (DueDate - CurrentTime) / ProcessingTime
            # Tránh chia 0
            pt = available_jobs['Processing Time'].replace(0, 0.1)
            cr = (available_jobs['Due Date'] - current_time) / pt
            best_job_idx = cr.idxmin()
            
        elif rule_code == "CUSTPR": # Ưu tiên cao nhất
            best_job_idx = available_jobs['Priority'].idxmax()
            
        elif rule_code == "SETUP": # Cùng loại setup
            # Nếu có job nào cùng loại setup với job vừa làm xong thì ưu tiên
            if scheduled_jobs and use_setup:
                last_setup = scheduled_jobs[-1]['Setup Type']
                same_setup_jobs = available_jobs[available_jobs['Setup Type'] == last_setup]
                if not same_setup_jobs.empty:
                    # Nếu có nhiều job cùng setup, dùng SPT để phá thế bí
                    best_job_idx = same_setup_jobs['Processing Time'].idxmin()
                else:
                    # Nếu không có, dùng SPT bình thường
                    best_job_idx = available_jobs['Processing Time'].idxmin()
            else:
                 best_job_idx = available_jobs['Processing Time'].idxmin()
        
        # 4. Thực hiện Job đã chọn
        job = remaining_jobs.loc[best_job_idx]
        
        start = current_time
        finish = start + job['Processing Time']
        late = max(0, finish - job['Due Date'])
        
        # Lưu kết quả
        scheduled_job = job.to_dict()
        scheduled_job['Start'] = start
        scheduled_job['Finish'] = finish
        scheduled_job['Lateness'] = late
        scheduled_jobs.append(scheduled_job)
        
        # Cập nhật thời gian và xóa job khỏi danh sách chờ
        current_time = finish
        remaining_jobs = remaining_jobs.drop(best_job_idx)

    return pd.DataFrame(scheduled_jobs)

# --- GIAO DIỆN CHÍNH ---
st.title("⏱️ Hệ thống Lập lịch Động (Dynamic Scheduling)")

if 'jobs' not in st.session_state:
    with st.spinner('Đang tải dữ liệu...'):
        st.session_state.jobs = get_data_from_github()

df_jobs = st.session_state.jobs

# --- KHU VỰC 1: INPUT ---
st.markdown("### 1. Dữ liệu đầu vào")
tab_manual, tab_random = st.tabs(["✍️ Nhập Thủ Công", "🎲 Tạo Ngẫu Nhiên"])

with tab_manual:
    with st.container(border=True):
        # Tính toán số cột cần hiển thị
        cols_count = 3 # ID, PT, DD
        if use_release: cols_count += 1
        if use_priority: cols_count += 1
        if use_setup: cols_count += 1
        cols_count += 1 # Button
        
        cols = st.columns(cols_count)
        idx = 0
        
        with cols[idx]: new_id = st.text_input("Job ID", placeholder="J1"); idx+=1
        
        new_rel = 0
        if use_release:
            with cols[idx]: new_rel = st.number_input("Release (Đến)", min_value=0, value=0); idx+=1
            
        with cols[idx]: new_pt = st.number_input("TG Xử lý", min_value=1, value=5); idx+=1
        with cols[idx]: new_dd = st.number_input("Hạn chót", min_value=1, value=15); idx+=1
        
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
                    new_row = {
                        'Job ID': str(new_id), 
                        'Release Time': int(new_rel),
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

# Cấu hình cột hiển thị
display_cols = ['Job ID']
if use_release: display_cols.append('Release Time')
display_cols.extend(['Processing Time', 'Due Date'])
if use_priority: display_cols.append('Priority')
if use_setup: display_cols.append('Setup Type')

col_config = {
    "Job ID": st.column_config.TextColumn("Job ID", required=True),
    "Release Time": st.column_config.NumberColumn("Release (Ngày đến)", min_value=0),
    "Processing Time": st.column_config.NumberColumn("TG Xử lý (Ngày)", min_value=1),
    "Due Date": st.column_config.NumberColumn("Hạn chót (Ngày)", min_value=1),
}

edited_df = st.data_editor(
    st.session_state.jobs[display_cols], 
    use_container_width=True, 
    num_rows="dynamic", 
    key="editor", 
    column_config=col_config
)

if st.button("💾 Lưu thay đổi bảng"):
    final_df = st.session_state.jobs.copy()
    # Fill default
    edited_df['Release Time'] = pd.to_numeric(edited_df.get('Release Time', 0)).fillna(0).astype(int)
    edited_df['Processing Time'] = pd.to_numeric(edited_df['Processing Time']).fillna(0).astype(int)
    edited_df['Due Date'] = pd.to_numeric(edited_df['Due Date']).fillna(0).astype(int)
    
    if save_data_to_github(edited_df, "Update table"):
        st.session_state.jobs = edited_df
        st.success("Đã lưu!")
        st.rerun()

# --- KHU VỰC 3: KẾT QUẢ ---
if not edited_df.empty:
    st.divider()
    
    # Map Rules
    rule_map = {
        "SPT - Ngắn nhất làm trước": "SPT",
        "LPT - Dài nhất làm trước": "LPT",
        "DDATE - Hạn chót sớm nhất (EDD)": "DDATE",
        "FCFS - Đến trước làm trước": "FCFS",
        "SLACK - Slack nhỏ nhất": "SLACK",
        "CR - Tỷ số tới hạn": "CR"
    }
    # Quy tắc phụ thuộc checkbox
    if use_priority: rule_map["CUSTPR - Ưu tiên khách hàng"] = "CUSTPR"
    if use_setup: rule_map["SETUP - Theo nhóm máy"] = "SETUP"

    # --- BENCHMARK ---
    st.header("📊 So sánh Hiệu quả")
    comp_data = []
    for name, code in rule_map.items():
        res = calculate_schedule(edited_df, code)
        comp_data.append({
            "Quy tắc": code, 
            "Tổng Trễ": res['Lateness'].sum(), 
            "Hoàn thành (Makespan)": res['Finish'].max(),
            "TB Lưu kho": round(res['Finish'].mean(), 2)
        })
    
    st.plotly_chart(px.bar(pd.DataFrame(comp_data), x="Quy tắc", y=["Tổng Trễ", "Hoàn thành", "TB Lưu kho"], barmode='group'), use_container_width=True)

    # --- GANTT CHART (TRỤC SỐ) ---
    st.divider()
    st.subheader("🔎 Chi tiết Lịch trình")
    
    selected_rule_name = st.selectbox("Chọn quy tắc:", list(rule_map.keys()))
    selected_rule_code = rule_map[selected_rule_name]
    
    result_df = calculate_schedule(edited_df, selected_rule_code)
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Makespan", f"{result_df['Finish'].max()} ngày")
    m2.metric("Tổng trễ", f"{result_df['Lateness'].sum()} ngày", delta_color="inverse")
    m3.metric("Số Job trễ", f"{(result_df['Lateness'] > 0).sum()}")

    # Vẽ Bar Chart kiểu Gantt
    color_col = "Setup Type" if selected_rule_code == "SETUP" else "Lateness"
    
    # Tạo tooltip thông minh
    result_df['Tooltip'] = result_df.apply(lambda x: f"Job: {x['Job ID']}<br>Start: {x['Start']}<br>Finish: {x['Finish']}<br>Late: {x['Lateness']}", axis=1)
    
    fig = px.bar(
        result_df,
        base="Start", x="Processing Time", y="Job ID", orientation='h',
        color=color_col,
        text="Processing Time",
        hover_data={"Tooltip": True, "Start": False, "Processing Time": False, "Job ID": False},
        title=f"Lịch trình - {selected_rule_name}",
        color_continuous_scale="RdYlGn_r" if color_col == "Lateness" else None
    )
    
    fig.update_layout(
        xaxis_title="Thời gian (Ngày thứ 0, 1, 2...)",
        yaxis=dict(autorange="reversed"),
        height=400 + (len(result_df) * 20)
    )
    st.plotly_chart(fig, use_container_width=True)
    
    with st.expander("Xem bảng chi tiết"):
        st.dataframe(result_df)
