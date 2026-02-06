import streamlit as st
import pandas as pd
from github import Github
import io

# --- CẤU HÌNH ---
st.set_page_config(page_title="Quản lý Điểm & Công Việc", layout="wide", page_icon="📝")

# Lấy thông tin từ secrets
GITHUB_TOKEN = st.secrets["github"]["token"]
REPO_NAME = st.secrets["github"]["repo_name"]
FILE_PATH = st.secrets["github"]["file_path"]

# --- HÀM TƯƠNG TÁC GITHUB ---
def get_data_from_github():
    """Đọc file CSV từ GitHub về"""
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        contents = repo.get_contents(FILE_PATH)
        decoded_content = contents.decoded_content.decode("utf-8")
        if not decoded_content:
            return pd.DataFrame(columns=["Mã HK", "Mã Môn", "Tên Môn", "TC", "Điểm"])
        return pd.read_csv(io.StringIO(decoded_content))
    except Exception as e:
        # Nếu file chưa tồn tại hoặc lỗi
        return pd.DataFrame(columns=["Mã HK", "Mã Môn", "Tên Môn", "TC", "Điểm"])

def save_data_to_github(df, commit_message):
    """Ghi đè file CSV mới lên GitHub"""
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        
        # Convert DataFrame sang CSV string
        csv_content = df.to_csv(index=False)
        
        try:
            # Thử lấy file cũ để update
            contents = repo.get_contents(FILE_PATH)
            repo.update_file(contents.path, commit_message, csv_content, contents.sha)
        except:
            # Nếu chưa có thì tạo mới
            repo.create_file(FILE_PATH, commit_message, csv_content)
        return True
    except Exception as e:
        st.error(f"Lỗi khi lưu GitHub: {e}")
        return False

# --- GIAO DIỆN CHÍNH ---
st.title("☁️ Quản lý Học phần (GitHub Sync)")

# 1. Load dữ liệu hiện tại
if 'data' not in st.session_state:
    with st.spinner('Đang tải dữ liệu từ GitHub...'):
        st.session_state.data = get_data_from_github()

df = st.session_state.data

# 2. Tạo Form nhập liệu (Giống ảnh)
with st.container(border=True):
    col1, col2, col3, col4, col5 = st.columns([1.5, 1.5, 4, 1, 1.5])
    
    with col1:
        ma_hk = st.text_input("Mã HK", placeholder="VD: 20261")
    with col2:
        ma_mon = st.text_input("Mã Môn", placeholder="VD: LOG101")
    with col3:
        ten_mon = st.text_input("Tên Môn", placeholder="VD: Logistics Căn bản")
    with col4:
        tc = st.number_input("TC", min_value=0, step=1, value=3)
    with col5:
        diem = st.number_input("Điểm", min_value=0.0, max_value=10.0, step=0.1, format="%.2f")

    # Các nút chức năng
    btn_col1, btn_col2, btn_col3 = st.columns(3)
    
    # --- XỬ LÝ NÚT THÊM ---
    if btn_col1.button("Thêm", use_container_width=True, type="primary"):
        if ma_mon and ten_mon:
            # Kiểm tra trùng lặp
            if ma_mon in df['Mã Môn'].values:
                st.warning(f"Môn {ma_mon} đã tồn tại! Hãy dùng nút Sửa.")
            else:
                new_row = pd.DataFrame({
                    "Mã HK": [ma_hk], "Mã Môn": [ma_mon], "Tên Môn": [ten_mon], 
                    "TC": [tc], "Điểm": [diem]
                })
                updated_df = pd.concat([df, new_row], ignore_index=True)
                
                # Lưu và cập nhật
                if save_data_to_github(updated_df, f"Add {ma_mon}"):
                    st.session_state.data = updated_df
                    st.success(f"Đã thêm môn {ma_mon}!")
                    st.rerun()
        else:
            st.error("Vui lòng nhập Mã Môn và Tên Môn")

    # --- XỬ LÝ NÚT SỬA ---
    if btn_col2.button("Sửa", use_container_width=True):
        if ma_mon in df['Mã Môn'].values:
            # Tìm index của dòng có mã môn tương ứng
            idx = df[df['Mã Môn'] == ma_mon].index[0]
            
            # Cập nhật giá trị
            df.at[idx, 'Mã HK'] = ma_hk
            df.at[idx, 'Tên Môn'] = ten_mon
            df.at[idx, 'TC'] = tc
            df.at[idx, 'Điểm'] = diem
            
            if save_data_to_github(df, f"Update {ma_mon}"):
                st.session_state.data = df
                st.success(f"Đã cập nhật môn {ma_mon}!")
                st.rerun()
        else:
            st.error(f"Không tìm thấy Mã môn {ma_mon} để sửa. Hãy kiểm tra lại.")

    # --- XỬ LÝ NÚT XÓA ---
    if btn_col3.button("Xóa", use_container_width=True):
        if ma_mon in df['Mã Môn'].values:
            updated_df = df[df['Mã Môn'] != ma_mon]
            
            if save_data_to_github(updated_df, f"Delete {ma_mon}"):
                st.session_state.data = updated_df
                st.success(f"Đã xóa môn {ma_mon}!")
                st.rerun()
        else:
            st.error(f"Không tìm thấy Mã môn {ma_mon} để xóa.")

# 3. Hiển thị bảng dữ liệu bên dưới
st.divider()
st.subheader("📋 Danh sách môn học")

# Hiển thị thống kê nhỏ
if not df.empty:
    gpa = (df['Điểm'] * df['TC']).sum() / df['TC'].sum() if df['TC'].sum() > 0 else 0
    st.info(f"Tổng số tín chỉ: {df['TC'].sum()} | GPA tạm tính: {gpa:.2f}")

st.dataframe(
    df, 
    use_container_width=True, 
    hide_index=True,
    column_config={
        "Điểm": st.column_config.NumberColumn(format="%.2f"),
        "TC": st.column_config.NumberColumn(format="%d")
    }
)
