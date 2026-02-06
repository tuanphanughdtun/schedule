import streamlit as st
import pandas as pd
import plotly.express as px
from github import Github
import io
import random

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="Production Scheduling System", layout="wide", page_icon="🏭")

# --- KẾT NỐI GITHUB ---
try:
    GITHUB_TOKEN = st.secrets["github"]["token"]
    REPO_NAME = st.secrets["github"]["repo_name"]
    FILE_PATH = "jobs_data_v5.csv" # Đổi tên file để update cấu trúc mới
except:
    st.error("⚠️ Chưa cấu hình Secrets! Hãy kiểm tra lại file .streamlit/secrets.toml")
    st.stop()

# --- SIDEBAR CẤU HÌNH ---
st.sidebar.header("⚙️ Cấu hình Dữ liệu")
use_release = st.sidebar.checkbox("Sử dụng Release Time (Thời điểm đến)", value=False) # Mặc định tắt cho giống bài tập cơ bản
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
        
        # Ép kiểu dữ liệu an toàn
        df['Job ID'] = df['Job ID'].astype(str)
        df['Processing Time'] = pd.to_numeric(df['Processing Time'], errors='coerce').fillna(0).astype(int)
        df['Due Date'] = pd.to_numeric(df['Due Date'], errors='coerce').fillna(0).astype(int)
        
        # Tạo cột mặc định
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
        rel = random.randint(0, 5) if use_release else 0
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

# --- LOGIC TÍNH TOÁN LỊCH TRÌNH ---
def calculate_schedule(df, rule_code):
    remaining_jobs = df.copy()
    
    # Ép kiểu số
    remaining_jobs['Release Time'] = pd.to_numeric(remaining_jobs['Release Time']).fillna(0) if use_release else 0
    remaining_jobs['Processing Time'] = pd.to_numeric(remaining_jobs['Processing Time']).fillna(0)
    remaining_jobs['Due Date'] = pd.to_numeric(remaining_jobs['Due Date']).fillna(0)
    if use_priority: remaining_jobs['Priority'] = pd.to_numeric(remaining_jobs['Priority']).fillna(1)
    
    current_time = 0
    scheduled_jobs = []
    
    # Vòng lặp mô phỏng
    while not remaining_jobs.empty:
        available_mask = remaining_jobs['Release Time'] <= current_time
        available_jobs = remaining_jobs[available_mask]
        
        if available_jobs.empty:
            next_arrival = remaining_jobs['Release Time'].min()
            current_time = next_arrival if next_arrival > current_time else current_time + 1
            continue 
            
        best_job_idx = None
        
        # Các quy tắc chọn Job
        if rule_code == "SPT": best_job_idx = available_jobs['Processing Time'].idxmin()
        elif rule_code == "LPT": best_job_idx = available_jobs['Processing Time'].idxmax()
        elif rule_code == "DDATE": best_job_idx = available_jobs['Due Date'].idxmin()
        elif rule_code == "FCFS": best_job_idx = available_jobs['Release Time'].idxmin() # Nếu cùng Release thì theo Index
        elif rule_code == "LCFS": best_job_idx = available_jobs.index.max() # Index lớn nhất (vào sau cùng)
        elif rule_code == "SLACK": 
            slacks = available_jobs['Due Date'] - current_time - available_jobs['Processing Time']
            best_job_idx = slacks.idxmin()
        elif rule_code == "CR": 
            pt = available_jobs['Processing Time'].replace(0, 0.1)
            cr = (available_jobs['Due Date'] - current_time) / pt
            best_job_idx = cr.idxmin()
        elif rule_code == "CUSTPR": best_job_idx = available_jobs['Priority'].idxmax()
        elif rule_code == "SETUP": 
            if scheduled_jobs and use_setup:
                last_setup = scheduled_jobs[-1]['Setup Type']
                same_setup = available_jobs[available_jobs['Setup Type'] == last_setup]
                best_job_idx = same_setup['Processing Time'].idxmin() if not same_setup.empty else available_jobs['Processing Time'].idxmin()
            else:
                 best_job_idx = available_jobs['Processing Time'].idxmin()
        
        if best_job_idx is None: 
            # Fallback nếu không chọn được (thường là FCFS trong nhóm available)
            best_job_idx = available_jobs.index[0]

        job = remaining_jobs.loc[best_job_idx]
        start = current_time
        finish = start + job['Processing Time']
        late = max(0, finish - job['Due Date'])
        flow_time = finish - job['Release Time'] # Flow Time = Finish - Arrival
        
        scheduled_job = job.to_dict()
        scheduled_job['Start'] = start
        scheduled_job['Finish'] = finish
        scheduled_job['Flow Time'] = flow_time
        scheduled_job['Lateness'] = late
        scheduled_jobs.append(scheduled_job)
        
        current_time = finish
        remaining_jobs = remaining_jobs.drop(best_job_idx)

    if not scheduled_jobs:
        return pd.DataFrame()
        
    return pd.DataFrame(scheduled_jobs)

# --- HÀM TÍNH TOÁN CÁC CHỈ SỐ (METRICS) THEO BÀI HỌC ---
def calculate_metrics(df_result):
    if df_result.empty: return {}
    
    sum_flow_time = df_result['Flow Time'].sum()
    sum_work_time = df_result['Processing Time'].sum()
    sum_lateness = df_result['Lateness'].sum()
    num_jobs = len(df_result)
    
    # Công thức theo ảnh
    avg_completion_time = sum_flow_time / num_jobs
    utilization = (sum_work_time / sum_flow_time) * 100 # Đơn vị %
    avg_jobs_in_system = sum_flow_time / sum_work_time
    avg_lateness = sum_lateness / num_jobs
    
    return {
        "Sum Flow Time": sum_flow_time,
        "Sum Work Time": sum_work_time,
        "Avg Completion Time": avg_completion_time,
        "Utilization (%)": utilization,
        "Avg Jobs in System": avg_jobs_in_system,
        "Avg Lateness": avg_lateness
    }

# --- GIAO DIỆN CHÍNH ---
st.title("🏭 Hệ thống Điều độ Sản xuất")

if 'jobs' not in st.session_state:
    with st.spinner('Đang tải dữ liệu...'):
        st.session_state.jobs = get_data_from_github()

df_jobs = st.session_state.jobs

# --- KHU VỰC 1: INPUT ---
st.markdown("### 1. Dữ liệu đầu vào")
tab_manual, tab_random = st.tabs(["✍️ Nhập Thủ Công", "🎲 Tạo Ngẫu Nhiên"])

with tab_manual:
    with st.container(border=True):
        cols_count = 3
        if use_release: cols_count += 1
        if use_priority: cols_count += 1
        if use_setup: cols_count += 1
        cols_count += 1 
        
        cols = st.columns(cols_count)
        idx = 0
        
        with cols[idx]: new_id = st.text_input("Job ID", placeholder="A"); idx+=1
        
        new_rel = 0
        if use_release:
            with cols[idx]: new_rel = st.number_input("Release Time", min_value=0, value=0); idx+=1
            
        with cols[idx]: new_pt = st.number_input("Processing Time", min_value=1, value=6); idx+=1
        with cols[idx]: new_dd = st.number_input("Due Date", min_value=1, value=8); idx+=1
        
        new_prio = 1
        if use_priority:
            with cols[idx]: new_prio = st.number_input("Priority", 1, 10, 5); idx+=1
        new_setup = "A"
        if use_setup:
            with cols[idx]: new_setup = st.selectbox("Setup", ["A", "B", "C", "D"]); idx+=1
            
        with cols[idx]:
            st.write("")
            st.write("")
            if st.button("➕ Thêm", use_container_width=True):
                if new_id and new_id not in df_jobs['Job ID'].values:
                    new_row = {'Job ID': str(new_id), 'Release Time': int(new_rel), 'Processing Time': int(new_pt), 'Due Date': int(new_dd), 'Priority': int(new_prio), 'Setup Type': new_setup}
                    updated_df = pd.concat([df_jobs, pd.DataFrame([new_row])], ignore_index=True)
                    if save_data_to_github(updated_df, f"Add {new_id}"):
                        st.session_state.jobs = updated_df
                        st.success(f"Đã thêm {new_id}")
                        st.rerun()
                else:
                    st.warning("Trùng ID!")

with tab_random:
    c1, c2 = st.columns([3, 1])
    with c1: num_jobs = st.slider("Số lượng Job:", 5, 50, 5)
    with c2: 
        st.write("")
        if st.button("🎲 Tạo Mới", type="primary", use_container_width=True):
            random_df = generate_random_jobs(num_jobs)
            if save_data_to_github(random_df, "Gen Random"):
                st.session_state.jobs = random_df
                st.rerun()

# --- KHU VỰC 2: DANH SÁCH CÔNG VIỆC ---
st.markdown("### 2. Danh sách công việc")
display_cols = ['Job ID']
if use_release: display_cols.append('Release Time')
display_cols.extend(['Processing Time', 'Due Date'])
if use_priority: display_cols.append('Priority')
if use_setup: display_cols.append('Setup Type')

col_config = {
    "Job ID": st.column_config.TextColumn("Job ID", required=True),
    "Processing Time": st.column_config.NumberColumn("Processing Time", min_value=1),
    "Due Date": st.column_config.NumberColumn("Due Date", min_value=1),
}

edited_df = st.data_editor(st.session_state.jobs[display_cols], use_container_width=True, num_rows="dynamic", key="editor", column_config=col_config)

if st.button("💾 Lưu thay đổi bảng"):
    # Fill default values
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
    
    rule_map = {
        "FCFS - First Come First Served": "FCFS",
        "SPT - Shortest Processing Time": "SPT",
        "LPT - Longest Processing Time": "LPT",
        "DDATE - Earliest Due Date": "DDATE",
        "LCFS - Last Come First Served": "LCFS",
        "SLACK - Smallest Slack": "SLACK",
        "CR - Smallest Critical Ratio": "CR"
    }
    if use_priority: rule_map["CUSTPR - Highest Customer Priority"] = "CUSTPR"
    if use_setup: rule_map["SETUP - Similar Required Setups"] = "SETUP"

    # --- SO SÁNH (BENCHMARK) ---
    st.header("📊 Bảng So Sánh Các Quy Tắc")
    comp_data = []
    
    for name, code in rule_map.items():
        res = calculate_schedule(edited_df, code)
        if not res.empty:
            mets = calculate_metrics(res)
            comp_data.append({
                "Quy tắc": code,
                "Avg Completion Time": round(mets["Avg Completion Time"], 2),
                "Utilization (%)": round(mets["Utilization (%)"], 2),
                "Avg Jobs in System": round(mets["Avg Jobs in System"], 2),
                "Avg Lateness": round(mets["Avg Lateness"], 2)
            })
            
    if comp_data:
        df_comp = pd.DataFrame(comp_data)
        
        # Style bảng: Tô màu giá trị tốt nhất
        # Tốt nhất: Time & Jobs & Lateness (Thấp), Utilization (Cao)
        st.dataframe(
            df_comp.style.highlight_min(subset=["Avg Completion Time", "Avg Jobs in System", "Avg Lateness"], color='#dbf2ce')
                         .highlight_max(subset=["Utilization (%)"], color='#dbf2ce'),
            use_container_width=True
        )
        
        # Biểu đồ so sánh
        st.subheader("Biểu đồ so sánh")
        tab_c1, tab_c2 = st.tabs(["Thời gian & Số lượng", "Hiệu suất & Độ trễ"])
        
        with tab_c1:
            fig1 = px.bar(df_comp, x="Quy tắc", y=["Avg Completion Time", "Avg Jobs in System"], barmode='group', title="Chỉ số Thời gian & Số lượng (Thấp hơn là Tốt)")
            st.plotly_chart(fig1, use_container_width=True)
            
        with tab_c2:
            fig2 = px.bar(df_comp, x="Quy tắc", y=["Utilization (%)", "Avg Lateness"], barmode='group', title="Hiệu suất (Cao tốt) & Độ trễ (Thấp tốt)")
            st.plotly_chart(fig2, use_container_width=True)
            
    else:
        st.warning("Không có dữ liệu kết quả.")

    # --- CHI TIẾT LỊCH TRÌNH ---
    st.divider()
    st.subheader("🔎 Chi Tiết Lịch Trình (Single Rule)")
    
    selected_rule_name = st.selectbox("Chọn quy tắc:", list(rule_map.keys()))
    selected_rule_code = rule_map[selected_rule_name]
    
    result_df = calculate_schedule(edited_df, selected_rule_code)
    
    if not result_df.empty:
        # Tính metrics
        metrics = calculate_metrics(result_df)
        
        # Hiển thị 4 thẻ chỉ số như trong bài học
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Avg Completion Time", f"{metrics['Avg Completion Time']:.1f} days", help="Sum flow time / Number of jobs")
        c2.metric("Utilization", f"{metrics['Utilization (%)']:.1f}%", help="Total work time / Sum flow time")
        c3.metric("Avg Jobs in System", f"{metrics['Avg Jobs in System']:.2f} jobs", help="Sum flow time / Total work time")
        c4.metric("Avg Job Lateness", f"{metrics['Avg Lateness']:.1f} days", help="Total late days / Number of jobs")

        # GANTT CHART
        color_col = "Setup Type" if selected_rule_code == "SETUP" else "Lateness"
        
        # Tạo bản sao có Tooltip để vẽ
        chart_df = result_df.copy()
        chart_df['Tooltip'] = chart_df.apply(lambda x: f"Job: {x['Job ID']}<br>Start: {x['Start']}<br>Finish: {x['Finish']}<br>Flow: {x['Flow Time']}", axis=1)
        
        fig = px.bar(
            chart_df,
            base="Start", x="Processing Time", y="Job ID", orientation='h',
            color=color_col,
            text="Processing Time",
            hover_data={"Tooltip": True, "Start": False, "Processing Time": False, "Job ID": False},
            title=f"Sequence: {'-'.join(result_df['Job ID'].tolist())}",
            color_continuous_scale="RdYlGn_r" if color_col == "Lateness" else None
        )
        
        fig.update_layout(xaxis_title="Time", yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)
        
        # BẢNG CHI TIẾT (Xóa cột Tooltip, thêm cột Flow Time)
        with st.expander("Xem bảng dữ liệu chi tiết", expanded=True):
            # Chọn các cột cần hiển thị
            show_cols = ['Job ID', 'Processing Time', 'Flow Time', 'Due Date', 'Lateness', 'Start', 'Finish']
            st.dataframe(result_df[show_cols], use_container_width=True)
    else:
        st.info("Chưa có lịch trình nào được tạo.")
