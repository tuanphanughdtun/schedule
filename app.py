import streamlit as st
import pandas as pd
import plotly.express as px
from github import Github
import io

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="Hệ thống Điều độ Sản xuất", layout="wide", page_icon="🏭")

# Lấy thông tin từ secrets (như bạn đã cấu hình thành công)
try:
    GITHUB_TOKEN = st.secrets["github"]["token"]
    REPO_NAME = st.secrets["github"]["repo_name"]
    FILE_PATH = "jobs_data.csv" # Đổi tên file để không bị lẫn với file điểm
except:
    st.error("⚠️ Chưa cấu hình Secrets! Hãy kiểm tra lại file .streamlit/secrets.toml")
    st.stop()

# --- 1. HÀM TƯƠNG TÁC GITHUB (LƯU TRỮ ĐÁM MÂY) ---
def get_data_from_github():
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        contents = repo.get_contents(FILE_PATH)
        decoded = contents.decoded_content.decode("utf-8")
        if not decoded:
            return pd.DataFrame(columns=['Job ID', 'Processing Time', 'Due Date'])
        return pd.read_csv(io.StringIO(decoded))
    except:
        # Nếu chưa có file thì trả về bảng rỗng hoặc dữ liệu mẫu
        return pd.DataFrame({
            'Job ID': ['J1', 'J2', 'J3', 'J4'],
            'Processing Time': [10, 4, 8, 12],
            'Due Date': [15, 20, 10, 30]
        })

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

# --- 2. HÀM TÍNH TOÁN (SCHEDULING LOGIC) ---
def calculate_schedule(df, rule):
    data = df.copy()
    
    # Sắp xếp
    if rule == "FCFS": data = data.sort_index()
    elif rule == "SPT": data = data.sort_values(by="Processing Time")
    elif rule == "EDD": data = data.sort_values(by="Due Date")
    elif rule == "LPT": data = data.sort_values(by="Processing Time", ascending=False)
    elif rule == "STR": 
        data['Slack'] = data['Due Date'] - data['Processing Time']
        data = data.sort_values(by="Slack")

    # Tính toán
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
st.title("🏭 Web Điều độ Công việc (Cloud Sync)")

# Load dữ liệu
if 'jobs' not in st.session_state:
    with st.spinner('Đang tải dữ liệu công việc...'):
        st.session_state.jobs = get_data_from_github()

df_jobs = st.session_state.jobs

# --- KHU VỰC 1: QUẢN LÝ CÔNG VIỆC (INPUT/EDIT) ---
with st.expander("📝 Quản lý danh sách công việc (Input Data)", expanded=True):
    col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
    
    with col1: job_id = st.text_input("Tên CV (Job ID)", placeholder="VD: J1")
    with col2: proc_time = st.number_input("TG Xử lý (Processing Time)", min_value=1, value=10)
    with col3: due_date = st.number_input("Hạn chót (Due Date)", min_value=1, value=20)
    
    with col4:
        st.write("") # Spacer
        if st.button("➕ Thêm Công Việc", use_container_width=True):
            if job_id and job_id not in df_jobs['Job ID'].values:
                new_row = pd.DataFrame({'Job ID': [job_id], 'Processing Time': [proc_time], 'Due Date': [due_date]})
                updated_df = pd.concat([df_jobs, new_row], ignore_index=True)
                if save_data_to_github(updated_df, f"Add job {job_id}"):
                    st.session_state.jobs = updated_df
                    st.success(f"Đã thêm {job_id}")
                    st.rerun()
            else:
                st.warning("Tên công việc bị trùng hoặc để trống!")

    # Bảng dữ liệu thô (có nút xóa)
    st.markdown("### Danh sách hiện tại:")
    edited_df = st.data_editor(
        df_jobs, 
        num_rows="dynamic", 
        use_container_width=True,
        key="editor"
    )
    
    # Nút cập nhật nếu sửa trực tiếp trên bảng
    if st.button("💾 Lưu thay đổi trên bảng"):
        if save_data_to_github(edited_df, "Update table manually"):
            st.session_state.jobs = edited_df
            st.success("Đã lưu dữ liệu!")
            st.rerun()

# --- KHU VỰC 2: CHẠY ĐIỀU ĐỘ & KẾT QUẢ ---
st.divider()
st.header("🚀 Chạy Lập Lịch (Scheduling)")

rule = st.selectbox("Chọn quy tắc ưu tiên:", ["SPT", "EDD", "FCFS", "LPT", "STR"])

if not df_jobs.empty:
    result_df = calculate_schedule(df_jobs, rule)
    
    # Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Makespan (Hoàn thành)", f"{result_df['Finish'].max()} phút")
    c2.metric("Tổng độ trễ (Total Tardiness)", f"{result_df['Lateness'].sum()} phút")
    c3.metric("Số việc bị trễ", f"{(result_df['Lateness'] > 0).sum()} việc")

    # Gantt Chart
    st.subheader("Biểu đồ Gantt")
    # Tạo ngày giả định để vẽ cho đẹp
    base_date = pd.Timestamp("2024-01-01 08:00")
    gantt_data = result_df.copy()
    gantt_data['Start_Date'] = base_date + pd.to_timedelta(gantt_data['Start'], unit='m')
    gantt_data['Finish_Date'] = base_date + pd.to_timedelta(gantt_data['Finish'], unit='m')
    
    fig = px.timeline(
        gantt_data, 
        x_start="Start_Date", x_end="Finish_Date", 
        y="Job ID", color="Lateness",
        title=f"Lịch trình sản xuất theo {rule}",
        color_continuous_scale="RdYlGn_r"
    )
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)
    
    # Bảng kết quả chi tiết
    with st.expander("Xem bảng chi tiết"):
        st.dataframe(result_df)
else:
    st.info("Chưa có dữ liệu công việc để tính toán.")
