import streamlit as st
import pandas as pd
import plotly.express as px
from github import Github
import io
import random
import numpy as np

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="Production Scheduling Simulation", layout="wide", page_icon="🏭")

# --- KẾT NỐI GITHUB ---
try:
    GITHUB_TOKEN = st.secrets["github"]["token"]
    REPO_NAME = st.secrets["github"]["repo_name"]
    FILE_PATH = "jobs_data.csv"
except:
    st.error("⚠️ Chưa cấu hình Secrets! Hãy kiểm tra lại file .streamlit/secrets.toml")
    st.stop()

def get_data_from_github():
    """Lấy dữ liệu và làm sạch"""
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        contents = repo.get_contents(FILE_PATH)
        decoded = contents.decoded_content.decode("utf-8")
        if not decoded:
            return pd.DataFrame(columns=['Job ID', 'Processing Time', 'Due Date'])
        
        df = pd.read_csv(io.StringIO(decoded))
        # Ép kiểu dữ liệu an toàn
        df['Job ID'] = df['Job ID'].astype(str)
        df['Processing Time'] = pd.to_numeric(df['Processing Time'], errors='coerce').fillna(0).astype(int)
        df['Due Date'] = pd.to_numeric(df['Due Date'], errors='coerce').fillna(0).astype(int)
        return df
    except:
        return pd.DataFrame(columns=['Job ID', 'Processing Time', 'Due Date'])

def save_data_to_github(df, message):
    """Lưu dữ liệu lên GitHub"""
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
    """
    Tạo n công việc ngẫu nhiên nhưng hợp lý.
    - Processing Time (PT): 1 đến 30
    - Due Date (DD): PT + Random Slack. 
      Để 'khả thi', DD phải >= PT. Slack càng lớn thì càng dễ, càng nhỏ càng khó (dễ trễ).
    """
    jobs = []
    for i in range(1, n + 1):
        pt = random.randint(5, 30) # Thời gian xử lý từ 5 đến 30
        # Hạn chót = Thời gian xử lý + một khoảng dư (slack)
        # Slack ngẫu nhiên từ 0 đến n*2 để tạo áp lực tiến độ
        slack = random.randint(0, int(n * 2)) 
        dd = pt + slack 
        jobs.append({
            "Job ID": f"J{i}",
            "Processing Time": pt,
            "Due Date": dd
        })
    return pd.DataFrame(jobs)

# --- LOGIC TÍNH TOÁN ---
def calculate_schedule(df, rule_code):
    data = df.copy()
    
    # Đảm bảo dữ liệu số
    data['Processing Time'] = pd.to_numeric(data['Processing Time']).fillna(0)
    data['Due Date'] = pd.to_numeric(data['Due Date']).fillna(0)
    
    # Sắp xếp
    if rule_code == "SPT": data = data.sort_values(by="Processing Time")
    elif rule_code == "EDD": data = data.sort_values(by="Due Date")
    elif rule_code == "LPT": data = data.sort_values(by="Processing Time", ascending=False)
    elif rule_code == "STR": 
        data['Slack'] = data['Due Date'] - data['Processing Time']
        data = data.sort_values(by="Slack")
    # FCFS: giữ nguyên index

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
st.title("🏭 Web Điều độ Công việc & Mô phỏng")

# 1. Load dữ liệu
if 'jobs' not in st.session_state:
    with st.spinner('Đang đồng bộ dữ liệu...'):
        st.session_state.jobs = get_data_from_github()

df_jobs = st.session_state.jobs

# --- KHU VỰC 1: INPUT DỮ LIỆU (2 TAB) ---
st.markdown("### 1. Dữ liệu đầu vào")
tab_manual, tab_random = st.tabs(["✍️ Nhập Thủ Công", "🎲 Tạo Ngẫu Nhiên (Random)"])

# TAB 1: THỦ CÔNG
with tab_manual:
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([3, 3, 3, 2])
        with c1: new_id = st.text_input("Job ID", placeholder="VD: J1")
        with c2: new_pt = st.number_input("Thời gian xử lý", min_value=1, value=10)
        with c3: new_dd = st.number_input("Hạn chót (Due Date)", min_value=1, value=20)
        with c4:
            st.write("")
            st.write("")
            if st.button("➕ Thêm Job", use_container_width=True):
                if new_id and new_id not in df_jobs['Job ID'].values:
                    new_row = pd.DataFrame({'Job ID': [str(new_id)], 'Processing Time': [int(new_pt)], 'Due Date': [int(new_dd)]})
                    updated_df = pd.concat([df_jobs, new_row], ignore_index=True)
                    if save_data_to_github(updated_df, f"Add {new_id}"):
                        st.session_state.jobs = updated_df
                        st.success(f"Đã thêm {new_id}")
                        st.rerun()
                else:
                    st.warning("Job ID bị thiếu hoặc trùng!")

# TAB 2: NGẪU NHIÊN
with tab_random:
    with st.container(border=True):
        st.info("💡 Chức năng này sẽ tạo mới toàn bộ danh sách công việc. Dữ liệu cũ sẽ bị thay thế.")
        col_r1, col_r2 = st.columns([2, 1])
        with col_r1:
            num_jobs = st.number_input("Số lượng công việc muốn tạo:", min_value=5, max_value=500, value=10, step=5)
        with col_r2:
            st.write("")
            st.write("")
            if st.button("🎲 Tạo & Lưu Dữ Liệu Mới", type="primary", use_container_width=True):
                random_df = generate_random_jobs(num_jobs)
                if save_data_to_github(random_df, f"Generate {num_jobs} random jobs"):
                    st.session_state.jobs = random_df
                    st.success(f"Đã tạo thành công {num_jobs} công việc ngẫu nhiên!")
                    st.rerun()

# --- KHU VỰC 2: HIỂN THỊ VÀ SỬA ---
st.markdown("### 2. Danh sách công việc hiện tại")
edited_df = st.data_editor(
    st.session_state.jobs,
    use_container_width=True,
    num_rows="dynamic",
    key="editor",
    column_config={
        "Job ID": st.column_config.TextColumn("Job ID", required=True),
        "Processing Time": st.column_config.NumberColumn("Processing Time", min_value=0, format="%d"),
        "Due Date": st.column_config.NumberColumn("Due Date", min_value=0, format="%d"),
    }
)

if not edited_df.equals(st.session_state.jobs):
    if st.button("💾 Lưu cập nhật bảng"):
        # Ép kiểu trước khi lưu
        edited_df['Processing Time'] = pd.to_numeric(edited_df['Processing Time']).fillna(0).astype(int)
        edited_df['Due Date'] = pd.to_numeric(edited_df['Due Date']).fillna(0).astype(int)
        if save_data_to_github(edited_df, "Manual update"):
            st.session_state.jobs = edited_df
            st.success("Đã lưu!")
            st.rerun()

# --- KHU VỰC 3: KẾT QUẢ & SO SÁNH ---
if not edited_df.empty:
    st.divider()
    
    # 3.1. KẾT QUẢ CHI TIẾT (SINGLE RULE)
    st.markdown("### 3. Chi tiết lịch trình")
    rule_map = {
        "Shortest Processing Time (SPT)": "SPT",
        "Earliest Due Date (EDD)": "EDD",
        "First Come First Served (FCFS)": "FCFS",
        "Longest Processing Time (LPT)": "LPT",
        "Slack Time Remaining (STR)": "STR"
    }
    
    selected_rule_name = st.selectbox("Chọn quy tắc để xem chi tiết:", list(rule_map.keys()))
    selected_rule_code = rule_map[selected_rule_name]
    
    # Tính toán
    result_detail = calculate_schedule(edited_df, selected_rule_code)
    
    # Metrics
    m1, m2, m3 = st.columns(3)
    makespan = result_detail['Finish'].max()
    tardiness = result_detail['Lateness'].sum()
    mean_flow = result_detail['Finish'].mean()
    
    m1.metric("Makespan", f"{makespan}")
    m2.metric("Mean Flow Time", f"{mean_flow:.2f}")
    m3.metric("Total Tardiness", f"{tardiness}", delta_color="inverse") # inverse: thấp là tốt (xanh)

    # Gantt Chart
    base_date = pd.Timestamp("2024-01-01 08:00")
    gantt_data = result_detail.copy()
    gantt_data['Start_Date'] = base_date + pd.to_timedelta(gantt_data['Start'], unit='m')
    gantt_data['Finish_Date'] = base_date + pd.to_timedelta(gantt_data['Finish'], unit='m')
    
    fig = px.timeline(
        gantt_data, x_start="Start_Date", x_end="Finish_Date", y="Job ID", color="Lateness",
        title=f"Gantt Chart ({selected_rule_name})", color_continuous_scale="RdYlGn_r", text="Job ID"
    )
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)

    # 3.2. SO SÁNH (COMPARISON)
    st.divider()
    st.header("📊 So sánh hiệu quả các quy tắc (Benchmark)")
    st.markdown("Bảng dưới đây chạy tất cả các quy tắc để tìm ra phương án tối ưu nhất cho bộ dữ liệu hiện tại.")
    
    comparison_data = []
    rules_to_compare = ["SPT", "EDD", "FCFS", "LPT", "STR"]
    
    for r in rules_to_compare:
        res = calculate_schedule(edited_df, r)
        comparison_data.append({
            "Rule": r,
            "Total Tardiness (Trễ)": res['Lateness'].sum(),
            "Mean Flow Time (TB Lưu kho)": round(res['Finish'].mean(), 2),
            "Makespan (Hoàn thành)": res['Finish'].max(),
            "Số Job bị trễ": (res['Lateness'] > 0).sum()
        })
        
    comp_df = pd.DataFrame(comparison_data)
    
    # Tìm tốt nhất
    best_tardiness = comp_df.loc[comp_df['Total Tardiness (Trễ)'].idxmin()]['Rule']
    best_flow = comp_df.loc[comp_df['Mean Flow Time (TB Lưu kho)'].idxmin()]['Rule']
    
    col_res1, col_res2 = st.columns([2, 2])
    
    with col_res1:
        st.dataframe(comp_df.style.highlight_min(axis=0, color='lightgreen', subset=['Total Tardiness (Trễ)', 'Mean Flow Time (TB Lưu kho)']), use_container_width=True)
        st.success(f"🏆 Quy tắc giảm độ trễ tốt nhất: **{best_tardiness}**")
        st.info(f"⏱️ Quy tắc lưu kho (Flow time) tốt nhất: **{best_flow}**")
        
    with col_res2:
        # Vẽ biểu đồ so sánh Tardiness
        fig_comp = px.bar(
            comp_df, x="Rule", y="Total Tardiness (Trễ)", 
            color="Total Tardiness (Trễ)", title="So sánh Tổng độ trễ (Thấp hơn là tốt hơn)",
            color_continuous_scale="Reds"
        )
        st.plotly_chart(fig_comp, use_container_width=True)

else:
    st.info("Chưa có dữ liệu. Vui lòng thêm job hoặc tạo ngẫu nhiên.")
