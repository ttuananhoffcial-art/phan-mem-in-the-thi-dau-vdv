import pandas as pd
import streamlit as st
import os

def load_data(): 
    # CHỈ ĐỌC FILE TỪ Ổ CỨNG MÁY TÍNH (KHÔNG LÊN MẠNG NỮA)
    file_path = "data/danh_sach.csv"
    
    if not os.path.exists(file_path):
        st.error(f"🚨 LỖI: Chưa tìm thấy file tại thư mục: {file_path}. Hãy copy file danh_sach.csv vào thư mục data!")
        st.stop()
    
    try:
        # Ép kiểu string để giữ nguyên số 0 ở đầu mã
        df = pd.read_csv(file_path, dtype=str)
        df = df.dropna(how='all')
        df.columns = [str(c).strip().replace('\n', ' ').replace('\r', '') for c in df.columns]
        return df
    except Exception as e:
        st.error(f"🚨 Lỗi đọc file CSV trong máy: {e}")
        st.stop()

def get_don_vi_data(df, ma_don_vi):
    df_clean = df.copy()
    df_clean['Mã đơn vị'] = df_clean['Mã đơn vị'].astype(str).str.strip().str.upper()
    return df_clean[df_clean['Mã đơn vị'] == str(ma_don_vi).strip().upper()]

def get_hoc_vien_info(df_don_vi, ma_hv):
    ma_hv_clean = str(ma_hv).strip().upper()
    df_don_vi_clean = df_don_vi.copy()
    df_don_vi_clean['Mã hội viên'] = df_don_vi_clean['Mã hội viên'].astype(str).str.strip().str.upper()
    
    hv = df_don_vi_clean[df_don_vi_clean['Mã hội viên'] == ma_hv_clean]
    
    if hv.empty:
        return None
    return hv.iloc[0].to_dict()