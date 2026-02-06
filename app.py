import streamlit as st
import pandas as pd
import plotly.express as px
from github import Github
import io

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="Production Scheduling", layout="wide", page_icon="🏭")

# --- KẾT NỐI GITHUB ---
try:
    GITHUB_TOKEN = st.secrets["github"]["token"]
    REPO_NAME = st.secrets["github"]["repo_name"]
    FILE_PATH = "jobs_data.csv"
except:
    st.error("⚠️ Chưa cấu hình Secrets! Hãy kiểm tra lại file .streamlit/secrets.toml")
    st.stop()

def get_data_from_github():
    """Lấy dữ liệu từ GitHub"""
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        contents = repo.get_contents(FILE_PATH)
        decoded = contents.decoded_content.decode("utf-8")
        if not decoded:
            return pd.DataFrame(columns=['Job ID', 'Processing Time', 'Due Date'])
        return pd.read_csv(io.StringIO(decoded))
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

# --- LOGIC TÍNH TOÁN ---
def calculate_schedule(df, rule_selection):
    data = df.copy()
    
    # --- [FIX BUG] CHUYỂN DỮ LIỆU VỀ DẠNG SỐ ---
    # Đảm bảo cột thời gian là số, nếu lỗi thì chuyển về 0
    data['Processing Time'] = pd.to_numeric(data['Processing Time'], errors='coerce').fillna(0)
    data['Due Date'] = pd.to_numeric(data['Due Date'], errors='coerce').fillna(0)
    # -------------------------------------------
    
    # Xử lý chuỗi quy tắc
    rule = rule_selection.split("(")[-1].replace(")", "")
    
    # Sắp xếp
    if rule == "FCFS": 
        pass 
    elif rule == "SPT": 
        data = data.sort_values(by="Processing Time")
    elif rule == "EDD": 
        data = data.sort_values(by="Due Date")
    elif rule == "LPT": 
        data = data.sort_values(by="Processing Time", ascending=False)
    elif rule == "STR": 
        data['Slack'] = data['Due Date'] - data['Processing Time']
        data = data.sort_values(by="Slack")

    # Tính toán
    current_time = 0
    start_times, finish_times, lateness = [], [], []
    
    for _, row in data.iterrows():
        start = current_time
        # Vì đã ép kiểu ở trên nên phép cộng này sẽ không bị lỗi nữa
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

# --- GIAO DIỆN NGƯỜI DÙNG ---
st.title("🏭 Web Điều độ Công việc")

# 1. Load dữ liệu
if 'jobs' not in st.session_state:
    with st.spinner('Đang đồng bộ dữ liệu...'):
        st.session_state.jobs = get_data_from_github()

df_jobs = st.session_state.jobs

# --- KHU VỰC NHẬP LIỆU ---
st.markdown("### 1. Nhập liệu nhanh")
with st.container(border=True):
    c1, c2, c3, c4 = st.columns([3, 3, 3, 2])
    
    with c1: new_id = st.text_input("Job ID", placeholder="VD: J10")
    with c2: new_pt = st.number_input("Processing Time", min_value=1, value=10)
    with c3: new_dd = st.number_input("Due Date", min_value=1, value=20)
    with c4:
        st.write("") 
        st.write("") 
        if st.button("➕ Thêm Job", use_container_width=True, type="primary"):
            if new_id and new_id not in df_jobs['Job ID'].values:
                # Tạo DataFrame mới đảm bảo đúng kiểu dữ liệu
                new_row = pd.DataFrame({
                    'Job ID': [str(new_id)], 
                    'Processing Time': [int(new_pt)], 
                    'Due Date': [int(new_dd)]
                })
                updated_df = pd.concat([df_jobs, new_row], ignore_index=True)
                if save_data_to_github(updated_df, f"Add {new_id}"):
                    st.session_state.jobs = updated_df
                    st.success(f"Đã thêm {new_id}")
                    st.rerun()
            else:
                st.warning("Job ID bị thiếu hoặc đã tồn tại!")

# --- KHU VỰC BẢNG DỮ LIỆU ---
st.markdown("### 2. Danh sách công việc (Sửa trực tiếp)")

# Cấu hình bảng để cột số chỉ nhận số (Tránh người dùng nhập chữ vào)
edited_df = st.data_editor(
    df_jobs,
    use_container_width=True,
    num_rows="dynamic",
    key="editor",
    column_config={
        "Processing Time": st.column_config.NumberColumn(min_value=0, format="%d"),
        "Due Date": st.column_config.NumberColumn(min_value=0, format="%d"),
        "Job ID": st.column_config.TextColumn(required=True)
    }
)

if not edited_df.equals(df_jobs):
    if st.button("💾 Lưu cập nhật bảng lên Cloud", type="primary"):
        if save_data_to_github(edited_df, "Update table"):
            st.session_state.jobs = edited_df
            st.success("Đã lưu thay đổi!")
            st.rerun()

# --- KHU VỰC ĐIỀU ĐỘ ---
st.divider()
st.markdown("### 3. Kết quả Điều độ (Scheduling Results)")

rule_options = [
    "Shortest Processing Time (SPT)",
    "Earliest Due Date (EDD)",
    "First Come First Served (FCFS)",
    "Longest Processing Time (LPT)",
    "Slack Time Remaining (STR)"
]

selected_rule = st.selectbox("Chọn quy tắc ưu tiên:", rule_options)

if not edited_df.empty:
    try:
        result_df = calculate_schedule(edited_df, selected_rule)
        
        # Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Makespan", f"{result_df['Finish'].max()}")
        m2.metric("Mean Flow Time", f"{result_df['Finish'].mean():.2f}")
        m3.metric("Total Tardiness", f"{result_df['Lateness'].sum()}")

        # Gantt Chart
        base_date = pd.Timestamp("2024-01-01 08:00")
        gantt_data = result_df.copy()
        gantt_data['Start_Date'] = base_date + pd.to_timedelta(gantt_data['Start'], unit='m')
        gantt_data['Finish_Date'] = base_date + pd.to_timedelta(gantt_data['Finish'], unit='m')
        
        fig = px.timeline(
            gantt_data, 
            x_start="Start_Date", x_end="Finish_Date", 
            y="Job ID", color="Lateness",
            title=f"Gantt Chart - {selected_rule}",
            color_continuous_scale="RdYlGn_r",
            text="Job ID"
        )
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Có lỗi khi tính toán: {e}. Vui lòng kiểm tra lại dữ liệu đầu vào.")
