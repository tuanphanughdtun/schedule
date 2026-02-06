import streamlit as st
import pandas as pd
import plotly.express as px
import io

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="Single Machine Scheduling", layout="wide", page_icon="🏭")

st.title("🏭 Single Machine Scheduling System")
st.markdown("### Teamwork Project 1: Programming Practical Classes")

# --- 1. HÀM TÍNH TOÁN (CORE LOGIC) ---
def calculate_schedule(df, rule):
    # Sao chép dữ liệu để không ảnh hưởng bản gốc
    data = df.copy()
    
    # Sắp xếp công việc theo quy tắc (Dispatching Rules)
    if rule == "FCFS (First Come First Served)":
        data = data.sort_index() # Giả sử index là thứ tự đến
    elif rule == "SPT (Shortest Processing Time)":
        data = data.sort_values(by="Processing Time")
    elif rule == "EDD (Earliest Due Date)":
        data = data.sort_values(by="Due Date")
    elif rule == "LPT (Longest Processing Time)":
        data = data.sort_values(by="Processing Time", ascending=False)
    elif rule == "STR (Slack Time Remaining)":
        # Slack = Due Date - Processing Time
        data['Slack'] = data['Due Date'] - data['Processing Time']
        data = data.sort_values(by="Slack")
    
    # Tính toán thời gian hoàn thành (Completion Time)
    current_time = 0
    start_times = []
    finish_times = []
    lateness = []
    flow_times = []

    for index, row in data.iterrows():
        start = max(current_time, 0) # Giả sử thời điểm đến = 0 cho đơn giản hóa (Single Machine basic)
        finish = start + row['Processing Time']
        
        start_times.append(start)
        finish_times.append(finish)
        
        # Flow Time = Finish - Arrival (Arrival = 0)
        flow_times.append(finish) 
        
        # Lateness = Finish - Due Date (nếu âm thì là 0 hoặc số âm tùy định nghĩa, ở đây lấy max(0, lateness) cho Tardiness)
        late = max(0, finish - row['Due Date'])
        lateness.append(late)
        
        current_time = finish

    data['Start Time'] = start_times
    data['Finish Time'] = finish_times
    data['Flow Time'] = flow_times
    data['Tardiness'] = lateness
    
    return data

# --- 2. GIAO DIỆN NHẬP LIỆU (INPUT DATA & OPEN DATA) ---
with st.sidebar:
    st.header("⚙️ Control Panel")
    
    # Upload File
    uploaded_file = st.file_uploader("📂 Open Data (CSV)", type=["csv"])
    
    # Template mẫu nếu chưa có data
    default_data = pd.DataFrame({
        'Job ID': ['J1', 'J2', 'J3', 'J4', 'J5'],
        'Processing Time': [10, 4, 8, 12, 6],
        'Due Date': [15, 20, 10, 30, 12]
    })

if uploaded_file is not None:
    try:
        input_df = pd.read_csv(uploaded_file)
        st.success("Đã tải dữ liệu thành công!")
    except:
        st.error("Lỗi định dạng file CSV.")
        input_df = default_data
else:
    st.info("Đang sử dụng dữ liệu mẫu. Bạn có thể tải lên file CSV hoặc chỉnh sửa trực tiếp bên dưới.")
    input_df = default_data

# Cho phép sửa dữ liệu trực tiếp trên bảng
st.subheader("1. Input Data")
edited_df = st.data_editor(input_df, num_rows="dynamic", use_container_width=True)

# --- 3. XỬ LÝ VÀ CHỌN QUY TẮC (DISPATCHING RULES) ---
st.subheader("2. Select Dispatching Rule")
rule = st.selectbox(
    "Chọn quy tắc ưu tiên (Priority Rule):",
    [
        "FCFS (First Come First Served)",
        "SPT (Shortest Processing Time)",
        "EDD (Earliest Due Date)",
        "LPT (Longest Processing Time)",
        "STR (Slack Time Remaining)"
    ]
)

if st.button("🚀 Run Scheduling"):
    # Chạy tính toán
    result_df = calculate_schedule(edited_df, rule)
    
    # --- 4. HIỂN THỊ KẾT QUẢ & BIỂU ĐỒ (GANTT CHART & REPORTS) ---
    st.divider()
    st.subheader(f"3. Results ({rule})")
    
    # Metrics tổng quan
    avg_flow_time = result_df['Flow Time'].mean()
    avg_tardiness = result_df['Tardiness'].mean()
    makespan = result_df['Finish Time'].max()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Makespan", f"{makespan} mins")
    col2.metric("Avg Flow Time", f"{avg_flow_time:.2f} mins")
    col3.metric("Avg Tardiness", f"{avg_tardiness:.2f} mins")

    # Hiển thị bảng kết quả chi tiết
    st.dataframe(result_df, use_container_width=True)

    # Vẽ Gantt Chart
    st.subheader("4. Gantt Chart")
    
    # Chuẩn bị data cho Plotly Timeline (cần convert sang datetime giả định để vẽ cho đẹp)
    # Vì Plotly timeline dùng ngày tháng, ta cộng phút vào một mốc thời gian giả định
    gantt_df = result_df.copy()
    base_date = pd.Timestamp('2024-01-01 08:00:00')
    gantt_df['Start'] = base_date + pd.to_timedelta(gantt_df['Start Time'], unit='m')
    gantt_df['Finish'] = base_date + pd.to_timedelta(gantt_df['Finish Time'], unit='m')
    
    fig = px.timeline(
        gantt_df, 
        x_start="Start", 
        x_end="Finish", 
        y="Job ID", 
        color="Tardiness", # Màu sắc cảnh báo độ trễ
        title=f"Gantt Chart - {rule}",
        labels={"Job ID": "Công việc"},
        color_continuous_scale="RdYlGn_r" # Đỏ là trễ nhiều, Xanh là ít trễ
    )
    fig.update_yaxes(autorange="reversed") # Job đầu tiên lên trên cùng
    st.plotly_chart(fig, use_container_width=True)

    # --- 5. XUẤT BÁO CÁO (EXPORT FRIENDLY REPORTS) ---
    st.subheader("5. Export Report")
    
    csv_buffer = result_df.to_csv(index=False).encode('utf-8')
    
    st.download_button(
        label="📥 Download Report (CSV)",
        data=csv_buffer,
        file_name=f"scheduling_report_{rule.split()[0]}.csv",
        mime="text/csv",
    )
