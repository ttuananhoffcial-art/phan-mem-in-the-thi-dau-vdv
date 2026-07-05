import streamlit as st
import urllib.parse
import requests
import json
import os
import re
import base64
import unicodedata
import io
import datetime
import zipfile
import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageOps
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, PageBreak, Paragraph, Spacer
from reportlab.platypus import Image as RLImage
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

try:
    from database.excel_handler import load_data
except:
    def load_data(): return pd.DataFrame()

# ==========================================
# CẤU HÌNH TRANG WEB & GIAO DIỆN CSS GLOBAL
# ==========================================
st.set_page_config(page_title="Phần Mềm Quản Lý Thẻ Taekwondo", page_icon="🏆", layout="wide")

st.markdown("""
    <style>
    input:disabled {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important; 
        font-weight: 600 !important; 
        background-color: #f0f2f6 !important;
    }
    
    .card-container {
        border: 1px solid #e0e0e0; border-radius: 12px; padding: 12px;
        box-shadow: 2px 4px 12px rgba(0,0,0,0.08); background-color: #ffffff;
        display: flex; flex-direction: column; height: 100%; transition: transform 0.2s;
    }
    .card-container:hover { transform: translateY(-5px); box-shadow: 2px 8px 15px rgba(0,0,0,0.15); }
    .card-img-wrapper {
        width: 100%; height: 240px; border-radius: 8px; overflow: hidden; margin-bottom: 12px;
        background-color: #f5f6fa; display: flex; align-items: center; justify-content: center;
    }
    .card-img-wrapper img { width: 100%; height: 100%; object-fit: cover; }
    .card-title { font-size: 18px; font-weight: 800; color: #2c3e50; margin-bottom: 8px; line-height: 1.3; text-transform: capitalize; }
    .card-text { font-size: 14px; margin: 0px 0px 5px 0px; color: #34495e; font-weight: 500; }
    .card-footer { font-size: 11px; color: #95a5a6; font-style: italic; margin-top: 10px; border-top: 1px dashed #ecf0f1; padding-top: 8px; }
    
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #f8f9fa; border-radius: 4px 4px 0px 0px; gap: 1px; padding-top: 10px; padding-bottom: 10px; }
    .stTabs [aria-selected="true"] { background-color: #e0f7fa; color: #2980b9; font-weight: bold; border-bottom: 3px solid #2980b9; }
    </style>
""", unsafe_allow_html=True)

CLIENT_ID = "411175345765-cuchaq5flnk6a16eboeu5k51fod89j64.apps.googleusercontent.com"
CLIENT_SECRET = "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"
REDIRECT_URI = "https://phan-mem-in-the-thi-dau-vdv.streamlit.app/"

CARDS_FILE = "data/submitted_cards.json"
CONFIG_GRAPHICS_FILE = "data/config_the.json"
AUTHORIZED_EMAILS = {"tuananht1kg@gmail.com": "ADMIN"}
AVATARS_DIR = "data/avatars"

if not os.path.exists(AVATARS_DIR):
    os.makedirs(AVATARS_DIR)

FIELD_OPTIONS = [
    "Họ và Tên", "Chức Vụ", "Năm sinh", "Đơn vị", "Nội dung (Hạng cân)",
    "Lứa tuổi", "Đẳng cấp", "Mã Hội Viên", "Đơn vị & Mã", "Mã Đơn vị gốc",
    "[Thông minh] Nội dung (VĐV) - Năm sinh (HLV)",
    "[Thông minh] Lứa tuổi (VĐV) - Chức vụ (HLV)", "Trống (Không in)"
]

# ==========================================
# KHỞI TẠO TRẠNG THÁI HỆ THỐNG
# ==========================================
for k in ['logged_in', 'user_email', 'user_role', 'user_unit', 'clear_form', 'approved_override_ma_hv', 'input_ma_hv', 'success_msg', 'success_url', 'edit_idx', 'show_settings', 'edit_tourney_idx']:
    if k not in st.session_state:
        st.session_state[k] = False if k in ['logged_in', 'clear_form', 'show_settings'] else (None if k in ['edit_idx', 'edit_tourney_idx'] else "")

if st.session_state['clear_form']:
    st.session_state['input_ma_hv'] = ""; st.session_state['approved_override_ma_hv'] = ""; st.session_state['clear_form'] = False

# ==============================================================
# QUẢN LÝ THAM SỐ VÀ CÀI ĐẶT
# ==============================================================
def process_and_save_image(uploaded_file, ma_hv):
    if uploaded_file is None: return ""
    try:
        img = Image.open(uploaded_file)
        if img.mode != 'RGB': img = img.convert('RGB')
        img.thumbnail((600, 800), Image.Resampling.LANCZOS)
        safe_id = re.sub(r'\W+', '_', str(ma_hv))
        filename = f"avatar_{safe_id}_{int(datetime.datetime.now().timestamp())}.jpg"
        filepath = os.path.join(AVATARS_DIR, filename)
        img.save(filepath, format="JPEG", quality=80)
        return filepath
    except Exception as e:
        st.error(f"Lỗi xử lý ảnh: {e}")
        return ""

def load_graphics_config():
    default_config = {
        "font_choice": "Arial", "img_x": 116, "img_y": 1380, "img_w": 586, "img_h": 800,
        "w_card_cm": 10.00, "h_card_cm": 14.00, "layout_pdf": "🔲 4 thẻ / 1 trang A4", "bg_option": "🖼️ In đầy đủ",
        "data_mapping": ["Họ và Tên", "Đơn vị", "[Thông minh] Nội dung (VĐV) - Năm sinh (HLV)", "[Thông minh] Lứa tuổi (VĐV) - Chức vụ (HLV)"],
        "lines": [
            {"color": "#ff0000", "initial_size": 95, "l_x": 1243, "l_y": 1780, "is_bold": True, "is_uppercase": False},
            {"color": "#000000", "initial_size": 109, "l_x": 1243, "l_y": 1894, "is_bold": True, "is_uppercase": False},
            {"color": "#000000", "initial_size": 100, "l_x": 1243, "l_y": 2048, "is_bold": True, "is_uppercase": False},
            {"color": "#000000", "initial_size": 85, "l_x": 1243, "l_y": 2201, "is_bold": True, "is_uppercase": False}
        ]
    }
    if not os.path.exists("data"): os.makedirs("data")
    if not os.path.exists(CONFIG_GRAPHICS_FILE):
        with open(CONFIG_GRAPHICS_FILE, "w", encoding="utf-8") as f: json.dump(default_config, f, indent=4)
    try:
        with open(CONFIG_GRAPHICS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "data_mapping" not in data: data["data_mapping"] = default_config["data_mapping"]
            data["font_choice"] = data.get("font_choice", "Arial").replace(" Bold", "")
            return data
    except: return default_config

def save_graphics_config(config):
    with open(CONFIG_GRAPHICS_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def remove_accents(input_str):
    nfkd_form = unicodedata.normalize('NFKD', str(input_str))
    only_ascii = u"".join([c for c in nfkd_form if not unicodedata.combining(c)])
    return only_ascii.replace("Đ", "D").replace("đ", "d")

def load_settings():
    default_data = {
        "unit_mapping": {}, "permissions": {}, "lua_tuoi": [], "noi_dung": [],
        "tournaments": [], "printed_status": {}
    }
    if not os.path.exists("data"): os.makedirs("data")
    if not os.path.exists("data/settings.json"):
        with open("data/settings.json", "w", encoding="utf-8") as f: json.dump(default_data, f)
    try:
        with open("data/settings.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            for k in ["lua_tuoi", "noi_dung"]: 
                if k not in data: data[k] = []
            if "unit_mapping" not in data: data["unit_mapping"] = {}
            if "tournaments" not in data: data["tournaments"] = []
            if "printed_status" not in data: data["printed_status"] = {}
            
            if "tournament_config" in data and data["tournament_config"].get("name"):
                if not data["tournaments"]:
                    old_t = data["tournament_config"]
                    old_t["is_active"] = True
                    data["tournaments"].append(old_t)
            return data
    except: return default_data

def save_settings(data):
    with open("data/settings.json", "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)

def mark_as_printed(tourney, unit):
    cur = load_settings()
    if "printed_status" not in cur: cur["printed_status"] = {}
    if tourney not in cur["printed_status"]: cur["printed_status"][tourney] = []
    if unit not in cur["printed_status"][tourney]:
        cur["printed_status"][tourney].append(unit)
    save_settings(cur)

def load_submitted_cards():
    if not os.path.exists(CARDS_FILE): return []
    try:
        with open(CARDS_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def save_submitted_card(card_data):
    cards = load_submitted_cards()
    cards.append(card_data)
    with open(CARDS_FILE, "w", encoding="utf-8") as f: json.dump(cards, f, ensure_ascii=False)

def set_edit_mode(idx): st.session_state['edit_idx'] = idx

def delete_card(idx):
    cards = load_submitted_cards()
    if 0 <= idx < len(cards):
        deleted_card = cards.pop(idx)
        img_path = deleted_card.get('Ảnh_Path', '')
        if img_path and os.path.exists(img_path):
            try: os.remove(img_path)
            except: pass
        with open(CARDS_FILE, "w", encoding="utf-8") as f: json.dump(cards, f, ensure_ascii=False)
        st.session_state['success_msg'] = f"🗑️ Đã XÓA hồ sơ của {deleted_card.get('Họ tên', '')}!"

def add_map():
    raw_text = st.session_state.map_email_input.lower()
    dv_moi = st.session_state.map_dv_select
    email_list = re.split(r'[, \n]+', raw_text)
    clean_emails = [e.strip() for e in email_list if "@gmail.com" in e.strip()]
    if clean_emails:
        cur = load_settings()
        for em in clean_emails: cur.setdefault("unit_mapping", {})[em] = dv_moi
        save_settings(cur); st.session_state.map_email_input = ""; st.session_state.thong_bao_mapping = f"✅ Gán thành công {len(clean_emails)} Gmail vào đơn vị {dv_moi}!"
    else: st.session_state.thong_bao_mapping = "❌ Lỗi: Không tìm thấy Gmail hợp lệ!"

def del_map(em):
    cur = load_settings()
    if em in cur.get("unit_mapping", {}): del cur["unit_mapping"][em]; save_settings(cur); st.session_state.thong_bao_mapping = f"🗑️ Đã xóa gán đơn vị của {em}!"

def add_q():
    em = st.session_state.nhap_q.strip().lower()
    if em and "@gmail.com" in em:
        cur = load_settings()
        if em not in cur.setdefault("permissions", {}):
            cur["permissions"][em] = {"xoa_danh_sach": False, "in_the": False}
            save_settings(cur); st.session_state.nhap_q = ""; st.session_state.thong_bao_quyen = f"✅ Đã cấp quyền cơ sở cho {em}!"
        else: st.session_state.thong_bao_quyen = f"⚠️ Tài khoản {em} đã tồn tại!"
    else: st.session_state.thong_bao_quyen = "❌ Vui lòng nhập đúng định dạng Gmail!"

def upd_q(em, q):
    cur = load_settings()
    if em in cur.get("permissions", {}): cur["permissions"][em][q] = st.session_state[f"{q}_{em}"]; save_settings(cur)

def del_q(em):
    cur = load_settings()
    if em in cur.get("permissions", {}): del cur["permissions"][em]; save_settings(cur); st.session_state.thong_bao_quyen = f"🗑️ Đã thu hồi toàn bộ quyền đặc biệt của {em}!"

def toggle_settings(): st.session_state['show_settings'] = not st.session_state['show_settings']

# ==============================================================
# TỪ ĐIỂN ÁNH XẠ MÃ TỈNH/THÀNH VÀ HÀM MAP DỮ LIỆU THÔNG MINH
# ==============================================================
UNIT_NAMES = {
    "AGIA": "An Giang", "BRVT": "Bà Rịa - Vũng Tàu", "BACL": "Bạc Liêu", "BGIA": "Bắc Giang", 
    "BKAN": "Bắc Kạn", "BNIN": "Bắc Ninh", "BENT": "Bến Tre", "BDIN": "Bình Định", 
    "BDUO": "Bình Dương", "BPHU": "Bình Phước", "BTHU": "Bình Thuận", "CMAU": "Cà Mau", 
    "CTHO": "Cần Thơ", "CBAN": "Cao Bằng", "DLAK": "Đắk Lắk", "DNON": "Đắk Nông", 
    "DBIE": "Điện Biên", "DNAI": "Đồng Nai", "DTHA": "Đồng Tháp", "GLAI": "Gia Lai", 
    "HAGI": "Hà Giang", "HNAM": "Hà Nam", "HANO": "Hà Nội", "HTIN": "Hà Tĩnh", 
    "HDUO": "Hải Dương", "HPHO": "Hải Phòng", "HAUG": "Hậu Giang", "HBIN": "Hòa Bình", 
    "HCMI": "TP. Hồ Chí Minh", "HYEN": "Hưng Yên", "KHOA": "Khánh Hòa", "KGIA": "Kiên Giang", 
    "KTUM": "Kon Tum", "LCHA": "Lai Châu", "LDON": "Lâm Đồng", "LSON": "Lạng Sơn", 
    "LCAI": "Lào Cai", "LANO": "Long An", "NDIN": "Nam Định", "NGAN": "Nghệ An", 
    "NBIN": "Ninh Bình", "NTHU": "Ninh Thuận", "PTHO": "Phú Thọ", "PYEN": "Phú Yên", 
    "QBIN": "Quảng Bình", "QNAM": "Quảng Nam", "QNGI": "Quảng Ngãi", "QNIN": "Quảng Ninh", 
    "QTRI": "Quảng Trị", "STRA": "Sóc Trăng", "SLAN": "Sơn La", "TNIN": "Tây Ninh", 
    "TBIN": "Thái Bình", "TNGU": "Thái Nguyên", "THAN": "Thanh Hóa", "TTHU": "Thừa Thiên Huế", 
    "TGIA": "Tiền Giang", "TVIN": "Trà Vinh", "TQUA": "Tuyên Quang", "VLON": "Vĩnh Long", 
    "VPHU": "Vĩnh Phúc", "YBAI": "Yên Bái", "CAND": "Công An Nhân Dân", "QDOI": "Quân Đội"
}

def get_full_unit_name(code):
    code_clean = str(code).strip().upper()
    return UNIT_NAMES.get(code_clean, code_clean)

def get_mapped_value(card, field_name):
    unit_full = get_full_unit_name(card.get("Đơn_vị", ""))
    cv_goc = str(card.get("Chức vụ", "")).strip()
    if not cv_goc: cv_goc = "VĐV"
    cv_upper = cv_goc.upper()
    if cv_upper in ["VĐV", "VDV"]: cv_full = "Vận Động Viên"
    elif cv_upper == "HLV": cv_full = "Huấn Luyện Viên"
    elif cv_upper in ["HLV TRƯỞNG", "HLV TRUONG"]: cv_full = "Huấn Luyện Viên Trưởng"
    elif cv_upper in ["TRƯỞNG ĐOÀN", "TRUONG DOAN"]: cv_full = "Trưởng Đoàn"
    else: cv_full = cv_goc

    if field_name == "Họ và Tên": return str(card.get("Họ tên", ""))
    elif field_name == "Chức Vụ": return cv_full
    elif field_name == "Năm sinh": return str(card.get("Năm sinh", ""))
    elif field_name == "Đơn vị": return unit_full
    elif field_name == "Đẳng cấp": return str(card.get("Đẳng cấp", ""))
    elif field_name == "Nội dung (Hạng cân)": return str(card.get("Nội dung", ""))
    elif field_name == "Lứa tuổi": return str(card.get("Lứa tuổi", ""))
    elif field_name == "Mã Hội Viên": return str(card.get("Mã", ""))
    elif field_name == "Đơn vị & Mã": return f"{unit_full} - Mã: {card.get('Mã', '')}"
    elif field_name == "Mã Đơn vị gốc": return str(card.get("Đơn_vị_gốc", card.get("Đơn_vị", "")))
    elif field_name == "[Thông minh] Nội dung (VĐV) - Năm sinh (HLV)":
        return str(card.get("Nội dung", "")) if cv_upper in ["VĐV", "VDV"] else f"Năm sinh: {card.get('Năm sinh', '')}"
    elif field_name == "[Thông minh] Lứa tuổi (VĐV) - Chức vụ (HLV)":
        return str(card.get("Lứa tuổi", "")) if cv_upper in ["VĐV", "VDV"] else cv_full
    return ""

# ==============================================================
# HÀM XUẤT FILE PDF DANH SÁCH (5 CỘT) + ZIP ẢNH
# ==============================================================
def tao_pdf_danh_sach(danh_sach_the, ten_don_vi):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=0.5*cm, leftMargin=0.5*cm, topMargin=1*cm, bottomMargin=1*cm)
    story = []

    font_paths = ["arial.ttf", "C:/Windows/Fonts/arial.ttf", "D:/Windows/Fonts/arial.ttf"]
    font_bold_paths = ["arialbd.ttf", "C:/Windows/Fonts/arialbd.ttf", "D:/Windows/Fonts/arialbd.ttf"]
    
    font_name = 'Helvetica'
    font_bold = 'Helvetica-Bold'
    
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont('VnFont', fp))
                font_name = 'VnFont'
                break
            except: pass
            
    for fbp in font_bold_paths:
        if os.path.exists(fbp):
            try:
                pdfmetrics.registerFont(TTFont('VnFont-Bold', fbp))
                font_bold = 'VnFont-Bold'
                break
            except: pass

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', fontName=font_bold, fontSize=16, alignment=1, spaceAfter=20, textColor='#2c3e50')
    text_style = ParagraphStyle('TextStyle', fontName=font_name, fontSize=8.5, leading=11, alignment=1)

    ten_day_du = get_full_unit_name(ten_don_vi).upper()
    story.append(Paragraph(f"DANH SÁCH NHÂN SỰ - {ten_day_du}", title_style))

    table_data = []
    row = []
    for c in danh_sach_the:
        cell_content = []
        
        img_data = None
        if "Ảnh_Path" in c and os.path.exists(c["Ảnh_Path"]):
            with open(c["Ảnh_Path"], "rb") as f: img_data = f.read()
        elif "Ảnh_Base64" in c and c["Ảnh_Base64"]:
            try: img_data = base64.b64decode(c["Ảnh_Base64"])
            except: pass
            
        if img_data:
            try:
                img = Image.open(io.BytesIO(img_data))
                img_w, img_h = img.size
                aspect = img_h / img_w
                rl_img = RLImage(io.BytesIO(img_data), width=3.0*cm, height=3.0*cm*aspect)
                cell_content.append(rl_img)
                cell_content.append(Spacer(1, 0.1*cm))
            except: pass

        cv = str(c.get("Chức vụ", "")).strip().upper()
        if cv in ["VĐV", "VDV", "VẬN ĐỘNG VIÊN"]: cv_hien_thi = "VĐV"
        elif cv in ["HLV", "HUẤN LUYỆN VIÊN"]: cv_hien_thi = "HLV"
        elif cv in ["HLV TRƯỞNG", "HLV TRUONG"]: cv_hien_thi = "HLV Trưởng"
        else: cv_hien_thi = c.get("Chức vụ", "")

        info_text = f"<font fontName='{font_bold}' size='9'>{c.get('Họ tên', '').upper()}</font><br/>"
        info_text += f"CV: <b>{cv_hien_thi}</b> | NS: {c.get('Năm sinh', '')}<br/>"
        if str(c.get('Đẳng cấp', '')).strip():
            info_text += f"Đẳng: {c.get('Đẳng cấp', '')}<br/>"
        info_text += f"Mã: {c.get('Mã', '')}<br/>"
        
        if cv in ["VĐV", "VDV", "VẬN ĐỘNG VIÊN"]:
            info_text += f"HC: {c.get('Nội dung', '')}<br/>"
            info_text += f"Tuổi: {c.get('Lứa tuổi', '')}"
            
        cell_content.append(Paragraph(info_text, text_style))
        row.append(cell_content)
        
        if len(row) == 5:
            table_data.append(row)
            row = []

    if row:
        while len(row) < 5: row.append("")
        table_data.append(row)

    if table_data:
        t = Table(table_data, colWidths=[4*cm]*5)
        t.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('INNERGRID', (0,0), (-1,-1), 0.25, '#ecf0f1'),
            ('BOX', (0,0), (-1,-1), 1, '#bdc3c7'),
            ('PADDING', (0,0), (-1,-1), 3),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("Chưa có dữ liệu.", text_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def tao_file_zip_xuat_du_lieu(danh_sach_the, ten_don_vi):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for c in danh_sach_the:
            img_bytes = None
            if "Ảnh_Path" in c and os.path.exists(c["Ảnh_Path"]):
                with open(c["Ảnh_Path"], "rb") as f: img_bytes = f.read()
            elif "Ảnh_Base64" in c and c["Ảnh_Base64"]:
                try: img_bytes = base64.b64decode(c["Ảnh_Base64"])
                except: pass
                
            if img_bytes:
                try:
                    safe_name = remove_accents(c.get("Họ tên", "")).replace(" ", "_").upper()
                    safe_cv = remove_accents(c.get("Chức vụ", "")).replace(" ", "")
                    safe_ma = c.get("Mã", "NoID")
                    file_name = f"Hinh_Anh/{safe_cv}_{safe_name}_{safe_ma}.jpg"
                    zip_file.writestr(file_name, img_bytes)
                except: pass

        if danh_sach_the:
            pdf_bytes = tao_pdf_danh_sach(danh_sach_the, ten_don_vi)
            zip_file.writestr(f"Danh_Sach_Nhan_Su_{ten_don_vi}.pdf", pdf_bytes)

    zip_buffer.seek(0)
    return zip_buffer.getvalue()

# ==============================================================
# LÕI THUẬT TOÁN ĐỒ HỌA PDF (IN THẺ)
# ==============================================================
def draw_card_image(card, g_cfg):
    STD_W = 2480
    aspect_ratio = g_cfg["h_card_cm"] / g_cfg["w_card_cm"]
    STD_H = int(STD_W * aspect_ratio) 
    
    vip_keywords = ["HLV", "HUAN LUYEN VIEN", "TRONG TAI", "BTC", "TRUONG DOAN", "BAN TO CHUC", "THU KY"]
    cv_goc = str(card.get("Chức vụ", "")).strip()
    if not cv_goc: cv_goc = "VĐV"
    is_vip = False
    chuc_vu_clean = remove_accents(cv_goc).upper()
    if any(kw in chuc_vu_clean for kw in vip_keywords): is_vip = True
            
    bg_choice = g_cfg.get("bg_option", "")
    if "Chỉ in nội dung" in bg_choice or "Nền trắng" in bg_choice:
        base_img = Image.new("RGBA", (STD_W, STD_H), (255, 255, 255, 255))
    else:
        phoi_path = "phoi_hlv.png" if is_vip else "phoi_vdv.png"
        if os.path.exists(phoi_path):
            img_temp = Image.open(phoi_path).convert("RGBA")
            base_img = ImageOps.fit(img_temp, (STD_W, STD_H), Image.Resampling.LANCZOS)
        else: base_img = Image.new("RGBA", (STD_W, STD_H), (255, 255, 255, 255))
            
    draw = ImageDraw.Draw(base_img)
    
    avatar = None
    if "Ảnh_Path" in card and os.path.exists(card["Ảnh_Path"]):
        try: avatar = Image.open(card["Ảnh_Path"]).convert("RGBA")
        except: pass
    elif "Ảnh_Base64" in card and card["Ảnh_Base64"]:
        try:
            avatar_data = base64.b64decode(card["Ảnh_Base64"])
            avatar = Image.open(io.BytesIO(avatar_data)).convert("RGBA")
        except: pass
        
    if avatar:
        try:
            avatar = ImageOps.fit(avatar, (g_cfg["img_w"], g_cfg["img_h"]), Image.Resampling.LANCZOS)
            base_img.paste(avatar, (g_cfg["img_x"], g_cfg["img_y"]), avatar)
        except: pass
        
    font_family = g_cfg.get("font_choice", "Arial")
    font_map = {
        "Arial": {"regular": "arial.ttf", "bold": "arialbd.ttf"},
        "Times New Roman": {"regular": "times.ttf", "bold": "timesbd.ttf"},
        "Tahoma": {"regular": "tahoma.ttf", "bold": "tahomabd.ttf"},
        "Calibri": {"regular": "calibri.ttf", "bold": "calibrib.ttf"}
    }
    
    max_safe_width = int(STD_W * 0.55)
    
    lines_text = [
        get_mapped_value(card, g_cfg["data_mapping"][0]),
        get_mapped_value(card, g_cfg["data_mapping"][1]),
        get_mapped_value(card, g_cfg["data_mapping"][2]),
        get_mapped_value(card, g_cfg["data_mapping"][3])
    ]
    
    for i, text_raw in enumerate(lines_text):
        if not text_raw: continue
        line_cfg = g_cfg["lines"][i]
        
        text_processed = text_raw.replace("HLV", "HUÂN LUYỆN VIÊN").replace("VĐV", "VẬN ĐỘNG VIÊN").replace("VDV", "VẬN ĐỘNG VIÊN")
        if line_cfg.get("is_uppercase", False): text_processed = text_processed.upper()
            
        hex_color = line_cfg["color"].lstrip('#')
        rgb_color = tuple(int(hex_color[j:j+2], 16) for j in (0, 2, 4))
        
        is_bold = line_cfg.get("is_bold", True)
        font_file = font_map.get(font_family, font_map["Arial"])["bold" if is_bold else "regular"]
        if not os.path.exists(font_file): font_file = "arial.ttf"

        current_size = line_cfg["initial_size"]
        selected_font = None
        
        while current_size >= 20:
            try: selected_font = ImageFont.truetype(font_file, current_size)
            except: selected_font = ImageFont.load_default()
            
            bbox = draw.textbbox((0, 0), text_processed, font=selected_font)
            text_w = bbox[2] - bbox[0]
            if text_w <= max_safe_width or current_size == 20: break
            current_size -= 2
            
        bbox = draw.textbbox((0, 0), text_processed, font=selected_font)
        text_w = bbox[2] - bbox[0]
        draw_x = line_cfg["l_x"] - (text_w // 2)
        draw_y = line_cfg["l_y"]
        
        draw.text((draw_x, draw_y), text_processed, fill=rgb_color, font=selected_font)
        
    return base_img.convert("RGB")

def export_reportlab_pdf(print_cards, g_cfg):
    pdf_buffer = io.BytesIO()
    w_pt = g_cfg["w_card_cm"] * cm
    h_pt = g_cfg["h_card_cm"] * cm
    
    if "1 thẻ" in g_cfg["layout_pdf"]:
        c = canvas.Canvas(pdf_buffer, pagesize=(w_pt, h_pt))
        for card in print_cards:
            pil_img = draw_card_image(card, g_cfg)
            img_byte_arr = io.BytesIO()
            pil_img.save(img_byte_arr, format='JPEG', quality=95)
            img_byte_arr.seek(0)
            rl_img = ImageReader(img_byte_arr)
            c.drawImage(rl_img, 0, 0, width=w_pt, height=h_pt, preserveAspectRatio=False)
            c.showPage()
        c.save()
    else:
        c = canvas.Canvas(pdf_buffer, pagesize=A4)
        page_w, page_h = A4
        block_w = 2 * w_pt
        block_h = 2 * h_pt
        start_x = (page_w - block_w) / 2.0
        start_y = (page_h - block_h) / 2.0
        
        chunks = [print_cards[i:i + 4] for i in range(0, len(print_cards), 4)]
        for chunk in chunks:
            for idx, card in enumerate(chunk):
                pil_img = draw_card_image(card, g_cfg)
                img_byte_arr = io.BytesIO()
                pil_img.save(img_byte_arr, format='JPEG', quality=95)
                img_byte_arr.seek(0)
                rl_img = ImageReader(img_byte_arr)
                
                row = idx // 2
                col = idx % 2
                
                draw_x = start_x + (col * w_pt)
                draw_y = start_y + ((1 - row) * h_pt)
                
                c.drawImage(rl_img, draw_x, draw_y, width=w_pt, height=h_pt, preserveAspectRatio=False)
            
            c.setStrokeColorRGB(0.8, 0.8, 0.8)
            c.setDash(2, 2)
            c.line(start_x + w_pt, start_y, start_x + w_pt, start_y + block_h)
            c.line(start_x, start_y + h_pt, start_x + block_w, start_y + h_pt)
            
            c.showPage()
        c.save()
        
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()

# ==========================================
# KHỞI CHẠY ĐỌC BỘ NHỚ ĐỆM HỆ THỐNG
# ==========================================
@st.cache_data
def init_data():
    def clean_df(df):
        if df is not None and not df.empty:
            # Tự động gọt dũa file khổng lồ (bỏ dòng/cột rác)
            df.dropna(how='all', inplace=True)
            df.columns = df.columns.astype(str).str.replace('\n', ' ').str.replace('\r', '').str.strip()
            
            # Bộ lọc nhận diện tên cột siêu thông minh
            col_mapping = {}
            for col in df.columns:
                col_lower = col.lower().strip()
                if any(x in col_lower for x in ['mã hội viên', 'số thẻ', 'mã vđv', 'mã hv', 'mã số', 'mã định danh']):
                    col_mapping[col] = 'Mã hội viên'
                elif any(x in col_lower for x in ['họ tên', 'họ và tên']):
                    col_mapping[col] = 'Họ và tên'
                elif 'sinh' in col_lower and 'nơi' not in col_lower:
                    col_mapping[col] = 'Năm sinh'
                elif any(x in col_lower for x in ['mã đơn vị', 'đơn vị tỉnh', 'đơn vị qg', 'mã tỉnh']):
                    col_mapping[col] = 'Mã đơn vị'
                elif any(x in col_lower for x in ['clb', 'võ đường', 'câu lạc bộ', 'cơ sở']):
                    col_mapping[col] = 'CLB/ Võ đường'
                elif any(x in col_lower for x in ['đẳng', 'cấp', 'đai']):
                    col_mapping[col] = 'Đẳng cấp'
            
            if 'Mã hội viên' not in col_mapping.values():
                for col in df.columns:
                    if col.lower().strip() == 'mã':
                        col_mapping[col] = 'Mã hội viên'

            df.rename(columns=col_mapping, inplace=True)
            
            for required_col in ['Mã hội viên', 'Họ và tên', 'Năm sinh', 'Mã đơn vị', 'CLB/ Võ đường', 'Đẳng cấp']:
                if required_col not in df.columns:
                    df[required_col] = ""
                    
            if 'Mã hội viên' in df.columns:
                df['Mã hội viên'] = df['Mã hội viên'].astype(str).str.strip()
        return df

    if os.path.exists("data/custom_database.csv"):
        try:
            df = pd.read_csv("data/custom_database.csv", dtype=str, encoding="utf-8-sig", on_bad_lines="skip").fillna("")
            if len(df.columns) == 1 and ';' in df.columns[0]:
                df = pd.read_csv("data/custom_database.csv", dtype=str, sep=";", encoding="utf-8-sig", on_bad_lines="skip").fillna("")
            return clean_df(df)
        except Exception:
            try:
                df = pd.read_csv("data/custom_database.csv", dtype=str, sep=";", encoding="cp1252", on_bad_lines="skip").fillna("")
                return clean_df(df)
            except:
                return clean_df(load_data())
    elif os.path.exists("data/custom_database.xlsx"):
        try:
            df = pd.read_excel("data/custom_database.xlsx", dtype=str).fillna("")
            return clean_df(df)
        except:
            return clean_df(load_data())
    return clean_df(load_data())

df_data = init_data()
settings_data = load_settings()
graphics_config = load_graphics_config()

tournaments_list = settings_data.get("tournaments", [])
active_tourneys = [t for t in tournaments_list if t.get("is_active")]
tourney_name = active_tourneys[0].get("name", "") if active_tourneys else ""

has_qgia = any(t.get("type", "QGIA") == "QGIA" for t in active_tourneys)
has_tinh = any(t.get("type", "QGIA") == "TINH" for t in active_tourneys)

today_date = datetime.date.today()
is_registration_open = False
date_err_msg = "THÔNG BÁO đã hết hạn nộp hồ sơ thẻ"

for t in active_tourneys:
    try:
        s_date_val = datetime.datetime.strptime(t.get('start_date', ''), "%Y-%m-%d").date()
        e_date_val = datetime.datetime.strptime(t.get('end_date', ''), "%Y-%m-%d").date()
        if s_date_val <= today_date <= e_date_val:
            is_registration_open = True
            break
        elif today_date < s_date_val:
            date_err_msg = f"THÔNG BÁO: Chưa đến thời gian đăng ký (Cổng sẽ mở từ ngày {t['start_date']})."
    except:
        is_registration_open = True

danh_sach_thuc_the_cai_dat = []
if df_data is not None:
    ds_qg = df_data.get('Mã đơn vị', pd.Series(dtype=str)).dropna().astype(str).str.strip().str.upper().unique().tolist()
    if "CAND" not in ds_qg: ds_qg.append("CAND")
    if "QDOI" not in ds_qg: ds_qg.append("QDOI")
    ds_ti = df_data.get('CLB/ Võ đường', pd.Series(dtype=str)).dropna().astype(str).str.strip().str.upper().unique().tolist()
    danh_sach_thuc_the_cai_dat = sorted(list(set(ds_qg + ds_ti)))

# ==========================================
# LOGIC XỬ LÝ ĐĂNG NHẬP GOOGLE OAUTH
# ==========================================
if not st.session_state['logged_in'] and "code" in st.query_params:
    code = st.query_params.get("code")
    try:
        token_url = "https://oauth2.googleapis.com/token"
        res = requests.post(token_url, data={"code": code, "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "redirect_uri": REDIRECT_URI, "grant_type": "authorization_code"})
        
        # Add a check to see if the request was successful
        if res.status_code == 200:
            access_token = res.json().get("access_token")
            user_info = requests.get("https://www.googleapis.com/oauth2/v1/userinfo", headers={"Authorization": f"Bearer {access_token}"}).json()
            email_dang_nhap = user_info.get("email", "").strip().lower()
            
            auth_emails_lower = {k.lower(): v for k, v in AUTHORIZED_EMAILS.items()}
            unit_mapping_lower = {k.lower(): v for k, v in settings_data.get("unit_mapping", {}).items()}
            perm_emails_lower = [e.lower() for e in settings_data.get("permissions", {}).keys()]
            
            if email_dang_nhap in auth_emails_lower: st.session_state.update({'logged_in': True, 'user_email': email_dang_nhap, 'user_role': "ADMIN", 'user_unit': ""}); st.query_params.clear(); st.rerun() 
            elif email_dang_nhap in unit_mapping_lower: st.session_state.update({'logged_in': True, 'user_email': email_dang_nhap, 'user_role': "DON_VI", 'user_unit': unit_mapping_lower[email_dang_nhap]}); st.query_params.clear(); st.rerun() 
            elif email_dang_nhap in perm_emails_lower: st.session_state.update({'logged_in': True, 'user_email': email_dang_nhap, 'user_role': "DON_VI_LE", 'user_unit': ""}); st.query_params.clear(); st.rerun()
            else: st.sidebar.error(f"❌ Tài khoản {email_dang_nhap} chưa được cấp quyền!"); st.query_params.clear()
        else:
            st.sidebar.error("Lỗi xác thực: Vui lòng thử đăng nhập lại.")
            st.query_params.clear()
            
    except Exception as e: st.sidebar.error(f"Có lỗi trong quá trình xác thực với Google: {e}")

st.sidebar.title("🔐 Đăng nhập hệ thống")
if not st.session_state['logged_in']:
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {"client_id": CLIENT_ID, "response_type": "code", "redirect_uri": REDIRECT_URI, "scope": "openid email profile", "prompt": "select_account"}
    login_url = f"{auth_url}?{urllib.parse.urlencode(params)}"
    st.sidebar.markdown(f'<a href="{login_url}" target="_top" style="text-decoration: none;"><div style="display: flex; align-items: center; justify-content: center; background-color: white; color: #3c4043; border: 1px solid #dadce0; border-radius: 4px; padding: 10px; font-weight: 500; cursor: pointer;"><img src="https://www.google.com/favicon.ico" style="width: 18px; margin-right: 12px;">Đăng nhập với Google</div></a>', unsafe_allow_html=True)
    st.info("👈 Vui lòng đăng nhập ở thanh bên trái để sử dụng phần mềm.")
    st.stop() 

st.sidebar.success("✅ Đăng nhập thành công!")
st.sidebar.markdown(f"**Tài khoản:** {st.session_state['user_email']}")
st.sidebar.markdown("---")

user_perms = settings_data.get("permissions", {}).get(st.session_state['user_email'], {})
quyen_in = user_perms.get("in_the", False)

if df_data is not None:
    menu_choice = st.sidebar.radio("📌 CHỨC NĂNG CHÍNH", ["1️⃣ Nộp Danh Sách Làm Thẻ", "2️⃣ In Thẻ", "3️⃣ Cài đặt"])
    st.sidebar.markdown("---")

    role = st.session_state['user_role']
    ma_don_vi_lam_viec = ""
    entity_label = "Đơn vị/CLB"

    all_cards_for_filter = load_submitted_cards()
    submitted_units = {str(c.get("Đơn_vị", "")).strip().upper() for c in all_cards_for_filter}

    if role == "ADMIN":
        st.sidebar.info("👑 Quyền: QUẢN TRỊ VIÊN")
        loai_giai_admin = st.sidebar.radio("🎯 Cấp độ Đơn vị làm việc:", ["Quốc Gia (Tỉnh/Ngành)", "Cấp Tỉnh (CLB)"])
        
        danh_sach_admin = []
        if "Quốc Gia" in loai_giai_admin:
            ds = df_data.get('Mã đơn vị', pd.Series(dtype=str)).dropna().astype(str).str.strip().str.upper().unique().tolist()
            if "CAND" not in ds: ds.append("CAND")
            if "QDOI" not in ds: ds.append("QDOI")
            danh_sach_admin = sorted([u for u in set(ds) if u.upper() in submitted_units])
            entity_label = "Đơn vị Tỉnh/Ngành"
        else:
            ds = df_data.get('CLB/ Võ đường', pd.Series(dtype=str)).dropna().astype(str).str.strip().str.upper().unique().tolist()
            danh_sach_admin = sorted([u for u in set(ds) if u.upper() in submitted_units])
            entity_label = "Câu Lạc Bộ"
            
        printed_status = settings_data.get("printed_status", {})
        printed_units = printed_status.get(tourney_name, [])
        
        def format_dv(dv):
            if dv == "-- Chọn --": return dv
            if dv in printed_units: return f"🟢 [Đã in] {dv}"
            return f"🔴 [Mới] {dv}"
            
        don_vi_chon = st.sidebar.selectbox(f"📌 Chọn {entity_label} (Chỉ hiện nơi đã nộp):", ["-- Chọn --"] + danh_sach_admin, format_func=format_dv)
        if don_vi_chon != "-- Chọn --": ma_don_vi_lam_viec = don_vi_chon
    elif role == "DON_VI":
        ma_don_vi_lam_viec = st.session_state['user_unit']
        st.sidebar.info("🏢 Quyền: ĐẠI DIỆN ĐƠN VỊ")
        st.sidebar.success(f"**Tài khoản của bạn: {ma_don_vi_lam_viec}**")
    else:
        st.sidebar.error("❌ Tài khoản chưa được gán Đơn vị!")
        st.sidebar.info("Vui lòng nhờ Admin gán Gmail này vào 1 Đơn vị.")
        
    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 LÀM MỚI TẢI LẠI DỮ LIỆU", type="primary", use_container_width=True): st.cache_data.clear(); st.rerun()
    if st.sidebar.button("Đăng xuất", use_container_width=True): st.session_state.clear(); st.cache_data.clear(); st.rerun()

    # ==========================================
    # MÀN HÌNH 1: NỘP DANH SÁCH LÀM THẺ 
    # ==========================================
    if menu_choice == "1️⃣ Nộp Danh Sách Làm Thẻ":
        st.title("📑 Nộp Danh Sách Làm Thẻ")
        
        if not active_tourneys:
            st.error("🚨 Không có giải đấu nào đang mở! Vui lòng nhờ Admin vào phần Cài Đặt -> Kích hoạt ít nhất 1 Giải đấu.")
            st.stop()

        banner_html = '<div style="background-color:#dff9fb; padding:15px; border-radius:8px; border-left: 5px solid #00a8ff; margin-bottom: 20px;">'
        banner_html += '<h4 style="margin:0; color:#273c75;">🏆 CÁC GIẢI ĐẤU ĐANG MỞ CỔNG ĐĂNG KÝ:</h4><ul style="margin:10px 0 0 0; padding-left: 20px; color:#353b48;">'
        for t in active_tourneys:
            t_type_str = 'Cấp Quốc Gia' if t.get('type') == 'QGIA' else 'Cấp Tỉnh/Thành'
            banner_html += f"<li><b>{t.get('name')}</b> (Từ {t.get('start_date')} đến {t.get('end_date')} | Quy mô: {t_type_str})</li>"
        banner_html += '</ul></div>'
        st.markdown(banner_html, unsafe_allow_html=True)

        if st.session_state['success_msg']:
            if "XÓA" not in st.session_state['success_msg']: st.balloons()
            st.success(st.session_state['success_msg'])
            if st.session_state['success_url']: st.markdown(f"🔗 **[Bấm vào đây để xem ảnh trên Drive]({st.session_state['success_url']})**")
            st.session_state['success_msg'] = ""; st.session_state['success_url'] = ""

        all_cards = load_submitted_cards()
        
        if st.session_state['edit_idx'] is not None:
            edit_i = st.session_state['edit_idx']
            if 0 <= edit_i < len(all_cards):
                if not is_registration_open and role != "ADMIN":
                    st.error(f"🚨 {date_err_msg}")
                    if st.button("🔙 Quay lại danh sách"):
                        st.session_state['edit_idx'] = None
                        st.rerun()
                    st.stop()
                    
                card_edit = all_cards[edit_i]
                st.markdown("---")
                st.markdown(f"<h3 style='color: #e67e22;'>✏️ Đang chỉnh sửa thẻ: {card_edit['Họ tên']} - {card_edit['Mã']}</h3>", unsafe_allow_html=True)
                
                c_e1, c_e2, c_e3 = st.columns([2, 2, 2])
                list_luatuoi = list(dict.fromkeys(["-- Chọn lứa tuổi --", "Không"] + settings_data.get("lua_tuoi", [])))
                list_noidung = list(dict.fromkeys(["-- Chọn nội dung --", "Không"] + settings_data.get("noi_dung", [])))
                
                with c_e1:
                    new_cv = st.selectbox("Chức vụ đoàn", ["VĐV", "HLV", "HLV Trưởng", "Trưởng đoàn"], index=["VĐV", "HLV", "HLV Trưởng", "Trưởng đoàn"].index(card_edit.get("Chức vụ", "VĐV")) if card_edit.get("Chức vụ", "VĐV") in ["VĐV", "HLV", "HLV Trưởng", "Trưởng đoàn"] else 0)
                    new_dc = st.text_input("Đẳng cấp", value=card_edit.get("Đẳng cấp", ""))
                with c_e2:
                    new_lt = st.selectbox("Lứa tuổi thi đấu", list_luatuoi, index=list_luatuoi.index(card_edit.get("Lứa tuổi","Không")) if card_edit.get("Lứa tuổi","Không") in list_luatuoi else 0)
                    new_nd = st.selectbox("Nội dung thi đấu", list_noidung, index=list_noidung.index(card_edit.get("Nội dung","Không")) if card_edit.get("Nội dung","Không") in list_noidung else 0)
                with c_e3:
                    new_file = st.file_uploader("Thay ảnh chân dung mới", type=['png', 'jpg', 'jpeg'])
                    
                if st.button("💾 Lưu cập nhật", type="primary"):
                    all_cards[edit_i]["Chức vụ"] = new_cv
                    all_cards[edit_i]["Lứa tuổi"] = new_lt
                    all_cards[edit_i]["Nội dung"] = new_nd
                    all_cards[edit_i]["Đẳng cấp"] = new_dc
                    if new_file is not None:
                        old_path = all_cards[edit_i].get("Ảnh_Path", "")
                        if old_path and os.path.exists(old_path):
                            try: os.remove(old_path)
                            except: pass
                        all_cards[edit_i]["Ảnh_Path"] = process_and_save_image(new_file, all_cards[edit_i].get("Mã", "NoID"))
                        if "Ảnh_Base64" in all_cards[edit_i]: del all_cards[edit_i]["Ảnh_Base64"]
                    with open(CARDS_FILE, "w", encoding="utf-8") as f: json.dump(all_cards, f, ensure_ascii=False)
                    st.session_state.update({'edit_idx': None, 'success_msg': "✅ Cập nhật hồ sơ thành công!"}); st.rerun()
            st.stop()

        if not ma_don_vi_lam_viec:
            if role == "ADMIN":
                st.warning("⚠️ Chọn Đơn vị ở menu bên trái để xem danh sách thẻ (Chỉ hiển thị đơn vị đã nộp).")
            else:
                st.warning(f"⚠️ Vui lòng liên hệ Admin để gán tài khoản vào {entity_label}!")
        else:
            st.text_input("🔍 Nhập Mã Hội Viên để tìm kiếm:", key="input_ma_hv").strip()
            ma_hv = st.session_state['input_ma_hv']
            
            if ma_hv:
                if not is_registration_open:
                    if role == "ADMIN":
                        st.warning(f"⚠️ {date_err_msg} (Admin đang được ưu tiên nộp quá hạn!)")
                    else:
                        st.error(f"🚨 {date_err_msg}")
                
                if is_registration_open or role == "ADMIN":
                    ma_hoi_vien_col = df_data.get('Mã hội viên', pd.Series(dtype=str))
                    if not ma_hoi_vien_col.empty:
                        df_data['Mã_So_Sanh'] = ma_hoi_vien_col.astype(str).str.upper().str.replace(" ", "")
                        ma_hv_clean = ma_hv.upper().replace(" ", "")
                        hv = df_data[df_data['Mã_So_Sanh'] == ma_hv_clean]
                        
                        if not hv.empty:
                            hv_info = hv.iloc[0].to_dict()
                            
                            dv_qgia = str(hv_info.get('Mã đơn vị', '')).strip().upper()
                            dv_tinh = str(hv_info.get('CLB/ Võ đường', '')).strip().upper()
                            
                            is_valid_unit = False
                            don_vi_goc = ""
                            error_msg = ""
                            
                            if has_qgia and ma_don_vi_lam_viec.upper() == dv_qgia:
                                is_valid_unit = True
                                don_vi_goc = dv_qgia
                            elif has_tinh and ma_don_vi_lam_viec.upper() == dv_tinh:
                                is_valid_unit = True
                                don_vi_goc = dv_tinh
                            else:
                                belong_to = []
                                if dv_qgia: belong_to.append(f"QG: {dv_qgia}")
                                if dv_tinh: belong_to.append(f"Tỉnh: {dv_tinh}")
                                error_msg = " / ".join(belong_to) if belong_to else "Không xác định"
                                don_vi_goc = dv_qgia if dv_qgia else dv_tinh 
                            
                            if is_valid_unit or st.session_state['approved_override_ma_hv'] == ma_hv:
                                ns_raw = str(hv_info.get('Năm sinh', hv_info.get('Ngày tháng năm sinh dd/mm/yyyy', '')))
                                ns_clean = ns_raw.split(" ")[0] if ns_raw != 'nan' else ""
                                nam_sinh = (ns_clean.split("-")[0] if "-" in ns_clean else ns_clean.split("/")[-1])[:4]
                                
                                dang_cap_goc = str(hv_info.get('Đẳng cấp', '')).replace('nan', '').strip()
                                
                                c1, c2 = st.columns(2)
                                with c1:
                                    cv_chon = st.selectbox("📌 Chức vụ đoàn", ["VĐV", "HLV", "HLV Trưởng", "Trưởng đoàn"])
                                    st.text_input("Họ và tên", value=hv_info.get('Họ và tên', ''), disabled=True)
                                    lt_chon = st.selectbox("Lứa tuổi", ["-- Chọn lứa tuổi --"] + settings_data.get("lua_tuoi", []))
                                    dc_chon = st.text_input("Đẳng cấp", value=dang_cap_goc)
                                with c2:
                                    nd_chon = st.selectbox("Nội dung tranh tài", ["-- Chọn nội dung --"] + settings_data.get("noi_dung", []))
                                    uploaded_file = st.file_uploader("Tải lên ảnh thẻ", type=['png', 'jpg', 'jpeg'])
                                    
                                if st.button("💾 Lưu hồ sơ", type="primary"):
                                    if uploaded_file:
                                        img_path = process_and_save_image(uploaded_file, ma_hv)
                                        save_submitted_card({
                                            "Người_nộp": st.session_state['user_email'], "Đơn_vị": ma_don_vi_lam_viec, 
                                            "Đơn_vị_gốc": don_vi_goc,
                                            "Mã": ma_hv, "Chức vụ": cv_chon, "Họ tên": hv_info.get('Họ và tên', ''),
                                            "Năm sinh": nam_sinh, "Nội dung": nd_chon, "Lứa tuổi": lt_chon, "Đẳng cấp": dc_chon,
                                            "Ảnh_Path": img_path
                                        })
                                        st.session_state.update({'success_msg': "✅ Đã ghi nhận hồ sơ mới!", 'clear_form': True}); st.rerun()
                                    else: st.warning("⚠️ Vui lòng cung cấp tệp ảnh thẻ!")
                            else:
                                st.error(f"🚨 Mã hội viên trực thuộc: **{error_msg}**! Không thuộc quyền quản lý của {ma_don_vi_lam_viec.upper()}.")
                                if st.button("✅ Xác nhận thi đấu đoàn mượn"):
                                    st.session_state['approved_override_ma_hv'] = ma_hv; st.rerun()
                        else: st.error("❌ Không tìm thấy mã hội viên trên hệ thống bản ghi gốc.")
                    else:
                        st.error("🚨 File CSDL gốc bị thiếu cột 'Mã hội viên'. Vui lòng tải lại file đúng chuẩn ở phần Cài đặt.")

        all_cards_updated = load_submitted_cards()
        display_cards = [c for c in all_cards_updated if ma_don_vi_lam_viec and ma_don_vi_lam_viec != "-- Chọn --" and str(c.get("Đơn_vị")).strip().upper() == ma_don_vi_lam_viec.upper()]
        
        if display_cards:
            st.markdown("<br><hr>", unsafe_allow_html=True)
            c_header, c_export, c_del = st.columns([2, 1, 1])
            with c_header: 
                st.subheader(f"🖼️ Danh sách thẻ đã đăng ký ({len(display_cards)} nhân sự)")
            
            with c_export:
                zip_data_export = tao_file_zip_xuat_du_lieu(display_cards, ma_don_vi_lam_viec)
                st.download_button(
                    label="📥 TẢI BÁO CÁO PDF & ẢNH (.ZIP)",
                    data=zip_data_export,
                    file_name=f"Ho_So_{ma_don_vi_lam_viec}.zip",
                    mime="application/zip",
                    use_container_width=True
                )

            if role == "ADMIN" and ma_don_vi_lam_viec:
                with c_del:
                    if st.button(f"🚨 XÓA TẤT CẢ", type="primary", use_container_width=True):
                        with st.spinner("Đang dọn dẹp dữ liệu (Có thể mất vài giây)..."):
                            all_remaining = []
                            deleted_count = 0
                            for c in all_cards_updated:
                                if str(c.get("Đơn_vị")).strip().upper() == ma_don_vi_lam_viec.upper(): 
                                    img_path = c.get('Ảnh_Path', '')
                                    if img_path and os.path.exists(img_path):
                                        try: os.remove(img_path)
                                        except: pass
                                    deleted_count += 1
                                else: all_remaining.append(c)
                            with open(CARDS_FILE, "w", encoding="utf-8") as f:
                                json.dump(all_remaining, f, ensure_ascii=False)
                            
                            cur_set_print = load_settings()
                            if "printed_status" in cur_set_print and tourney_name in cur_set_print["printed_status"]:
                                if ma_don_vi_lam_viec in cur_set_print["printed_status"][tourney_name]:
                                    cur_set_print["printed_status"][tourney_name].remove(ma_don_vi_lam_viec)
                                    save_settings(cur_set_print)
                                    
                            st.session_state['success_msg'] = f"✅ Đã xóa sạch {deleted_count} thẻ của {ma_don_vi_lam_viec}!"
                            st.rerun()
                            
            # --- TÍNH NĂNG PHÂN TRANG (CHỐNG SẬP GIAO DIỆN) ---
            ITEMS_PER_PAGE = 30
            total_pages = max(1, (len(display_cards) - 1) // ITEMS_PER_PAGE + 1)
            
            if total_pages > 1:
                st.markdown("---")
                page_num = st.number_input(f"📄 Phân trang (1 - {total_pages})", min_value=1, max_value=total_pages, value=1)
                start_idx = (page_num - 1) * ITEMS_PER_PAGE
                end_idx = start_idx + ITEMS_PER_PAGE
                paged_cards = display_cards[start_idx:end_idx]
                st.info(f"Đang hiển thị hồ sơ từ {start_idx + 1} đến {min(end_idx, len(display_cards))} (Tổng: {len(display_cards)})")
            else:
                paged_cards = display_cards

            for ten_cv in ["Trưởng đoàn", "HLV Trưởng", "HLV", "VĐV"]:
                nhom = [(i, c) for i, c in enumerate(all_cards_updated) if c in paged_cards and c.get("Chức vụ") == ten_cv]
                if nhom:
                    st.markdown(f"#### 📌 {ten_cv} ({len(nhom)})")
                    cols = st.columns(6)
                    for idx, (original_idx, card) in enumerate(nhom):
                        with cols[idx % 6]:
                            img_src = ""
                            if "Ảnh_Path" in card and os.path.exists(card["Ảnh_Path"]):
                                with open(card["Ảnh_Path"], "rb") as f:
                                    img_src = f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
                            elif "Ảnh_Base64" in card and card["Ảnh_Base64"]:
                                img_src = f"data:image/jpeg;base64,{card['Ảnh_Base64']}"
                                
                            html_content = f'<div class="card-container">'
                            html_content += f'<div class="card-img-wrapper"><img src="{img_src}"></div>'
                            html_content += f'<div class="card-title">{card.get("Họ tên", "")}</div>'
                            html_content += f'<div class="card-text">🏢 {get_full_unit_name(card.get("Đơn_vị", ""))}</div>'
                            html_content += f'<div class="card-text" style="color: #16a085; font-weight: bold;">🏷️ Mã gốc: {card.get("Đơn_vị_gốc", card.get("Đơn_vị", ""))}</div>'
                            html_content += f'<div class="card-text">🎂 NS: {card.get("Năm sinh", "")}</div>'
                            if str(card.get('Đẳng cấp', '')).strip():
                                html_content += f'<div class="card-text">🥋 Đẳng cấp: {card.get("Đẳng cấp", "")}</div>'
                            if card.get("Chức vụ") == "VĐV":
                                html_content += f'<div class="card-text" style="color: #0984e3; font-weight: bold;">🥋 {card.get("Nội dung", "")}</div>'
                                html_content += f'<div class="card-text" style="color: #e17055; font-weight: bold;">🏅 {card.get("Lứa tuổi", "")}</div>'
                            html_content += f'<div class="card-footer">👤 {card.get("Người_nộp", "")}</div></div>'
                            st.markdown(html_content, unsafe_allow_html=True)
                            
                            st.markdown("<div style='height: 5px;'></div>", unsafe_allow_html=True)
                            c_a1, c_a2 = st.columns(2)
                            with c_a1: 
                                if not is_registration_open and role != "ADMIN":
                                    st.button("✏️ Sửa", key=f"e_{original_idx}", disabled=True, use_container_width=True)
                                else:
                                    st.button("✏️ Sửa", key=f"e_{original_idx}", on_click=set_edit_mode, args=(original_idx,), use_container_width=True)
                            with c_a2: 
                                if not is_registration_open and role != "ADMIN":
                                    st.button("🗑️ Xóa", key=f"d_{original_idx}", disabled=True, use_container_width=True)
                                else:
                                    st.button("🗑️ Xóa", key=f"d_{original_idx}", on_click=delete_card, args=(original_idx,), use_container_width=True)

    # ==============================================================
    # 🖨️ MÀN HÌNH 2: PHÂN HỆ DÀN TRANG KẾT XUẤT FILE IN CHUYÊN NGHIỆP
    # ==============================================================
    elif menu_choice == "2️⃣ In Thẻ":
        st.markdown("<h1><span style='color:#8e44ad;'>➕</span> PHÂN HỆ CẤU HÌNH KÍCH THƯỚC & XUẤT BẢN PDF</h1>", unsafe_allow_html=True)
        st.markdown("---")
        
        if not ma_don_vi_lam_viec: 
            st.warning(f"⚠️ Vui lòng chọn Đơn vị ở Menu bên trái để tải danh sách thẻ!")
        elif role == "ADMIN" or quyen_in: 
            all_cards = load_submitted_cards()
            print_cards = [c for c in all_cards if str(c.get("Đơn_vị")).strip().upper() == ma_don_vi_lam_viec.upper()]
            
            if len(print_cards) == 0:
                st.warning(f"Đơn vị {ma_don_vi_lam_viec} hiện chưa có dữ liệu võ sinh đăng ký.")
            else:
                st.success(f"Tìm thấy {len(print_cards)} thẻ sẵn sàng. Bấm nút bên dưới để mở Bảng cấu hình xuất bản.")
                st.button("⚙️ BẤM VÀO ĐÂY ĐỂ CẤU HÌNH THÔNG SỐ ĐỒ HỌA IN THẺ", on_click=toggle_settings, type="primary")

                if st.session_state['show_settings']:
                    st.markdown("""<div style="background-color: #f4f6f9; padding: 25px; border-radius: 12px; margin-top: 15px; margin-bottom: 25px; border: 1px solid #dcdde1; box-shadow: 0px 5px 15px rgba(0,0,0,0.05);">""", unsafe_allow_html=True)
                    
                    st.markdown("### 📐 A. Cấu hình Kích thước Vật lý (Physical Dimension Parameters)")
                    col_k1, col_k2 = st.columns(2)
                    v_w_card_cm = col_k1.number_input("Chiều ngang thẻ (the_width_cm):", value=float(graphics_config.get("w_card_cm", 10.0)), step=0.10, format="%.2f", key="ui_w")
                    v_h_card_cm = col_k2.number_input("Chiều cao thẻ (the_height_cm):", value=float(graphics_config.get("h_card_cm", 14.0)), step=0.10, format="%.2f", key="ui_h")
                    
                    st.markdown("### 🎛️ B. Thuật toán Bố cục PDF (PDF Layout Engine) & C. Lớp phủ Nền đồ họa")
                    col_k3, col_k4 = st.columns(2)
                    v_layout_pdf = col_k3.radio("Chọn bố cục dàn trang kết xuất file PDF:", ["🔲 4 thẻ / 1 trang A4", "📄 1 thẻ / 1 trang"], index=0 if "4 thẻ" in graphics_config.get("layout_pdf","") else 1, key="ui_lay")
                    v_bg_option = col_k4.radio("Tùy chọn nền phôi đồ họa:", ["🖼️ In đầy đủ", "⬜ Chỉ in nội dung"], index=0 if "đầy đủ" in graphics_config.get("bg_option","") else 1, key="ui_bg")
                    
                    st.markdown("<hr style='margin:15px 0px; border-color:#e0e0e0;'>", unsafe_allow_html=True)
                    st.markdown("### ⚙️ Căn chỉnh Tọa độ Ảnh chân dung (Image Position Bounds) & Text Layer")
                    v_font_choice = st.selectbox("Chọn Họ Phông chữ Windows (Font Engine):", ["Arial", "Times New Roman", "Tahoma", "Calibri"], index=["Arial", "Times New Roman", "Tahoma", "Calibri"].index(graphics_config.get("font_choice", "Arial")), key="ui_font")
                    
                    tab_photo, tab_l12, tab_l34 = st.tabs(["📷 Ảnh chân dung (Bounds)", "🔤 Dòng 1 & Dòng 2", "🔤 Dòng 3 & Dòng 4"])
                    with tab_photo:
                        col_img1, col_img2 = st.columns(2)
                        v_img_x = col_img1.number_input("Vị trí ngang X (Ảnh)", value=int(graphics_config.get("img_x", 116)), key="ui_ix")
                        v_img_y = col_img2.number_input("Vị trí dọc Y (Ảnh)", value=int(graphics_config.get("img_y", 1380)), key="ui_iy")
                        v_img_w = col_img1.number_input("Chiều rộng khung ảnh (img_w)", value=int(graphics_config.get("img_w", 586)), key="ui_iw")
                        v_img_h = col_img2.number_input("Chiều cao khung ảnh (img_h)", value=int(graphics_config.get("img_h", 800)), key="ui_ih")
                    with tab_l12:
                        st.markdown("🔹 **Cấu hình Dòng 1**")
                        cx1_1, cx1_2, cx1_3 = st.columns([1,1,1])
                        v_color_line1 = cx1_1.color_picker("🎨 Màu sắc:", graphics_config["lines"][0]["color"], key="c1")
                        with cx1_2: st.write(""); v_is_bold1 = st.checkbox("𝗕 In đậm (Bold)", value=graphics_config["lines"][0].get("is_bold", True), key="b1")
                        with cx1_3: st.write(""); v_is_up1 = st.checkbox("🔠 Viết hoa (UPPER)", value=graphics_config["lines"][0].get("is_uppercase", False), key="u1")
                        cl1_1, cl1_2, cl1_3 = st.columns(3)
                        v_size_line1 = cl1_1.number_input("Cỡ chữ Dòng 1", value=int(graphics_config["lines"][0]["initial_size"]), key="s1")
                        v_x_line1 = cl1_2.number_input("Tâm X Dòng 1", value=int(graphics_config["lines"][0]["l_x"]), key="x1")
                        v_y_line1 = cl1_3.number_input("Vị trí Y Dòng 1", value=int(graphics_config["lines"][0]["l_y"]), key="y1")
                        
                        st.markdown("🔹 **Cấu hình Dòng 2**")
                        cx2_1, cx2_2, cx2_3 = st.columns([1,1,1])
                        v_color_line2 = cx2_1.color_picker("🎨 Màu sắc:", graphics_config["lines"][1]["color"], key="c2")
                        with cx2_2: st.write(""); v_is_bold2 = st.checkbox("𝗕 In đậm (Bold)", value=graphics_config["lines"][1].get("is_bold", True), key="b2")
                        with cx2_3: st.write(""); v_is_up2 = st.checkbox("🔠 Viết hoa (UPPER)", value=graphics_config["lines"][1].get("is_uppercase", False), key="u2")
                        cl2_1, cl2_2, cl2_3 = st.columns(3)
                        v_size_line2 = cl2_1.number_input("Cỡ chữ Dòng 2", value=int(graphics_config["lines"][1]["initial_size"]), key="s2")
                        v_x_line2 = cl2_2.number_input("Tâm X Dòng 2", value=int(graphics_config["lines"][1]["l_x"]), key="x2")
                        v_y_line2 = cl2_3.number_input("Vị trí Y Dòng 2", value=int(graphics_config["lines"][1]["l_y"]), key="y2")
                    with tab_l34:
                        st.markdown("🔹 **Cấu hình Dòng 3**")
                        cx3_1, cx3_2, cx3_3 = st.columns([1,1,1])
                        v_color_line3 = cx3_1.color_picker("🎨 Màu sắc:", graphics_config["lines"][2]["color"], key="c3")
                        with cx3_2: st.write(""); v_is_bold3 = st.checkbox("𝗕 In đậm (Bold)", value=graphics_config["lines"][2].get("is_bold", True), key="b3")
                        with cx3_3: st.write(""); v_is_up3 = st.checkbox("🔠 Viết hoa (UPPER)", value=graphics_config["lines"][2].get("is_uppercase", False), key="u3")
                        cl3_1, cl3_2, cl3_3 = st.columns(3)
                        v_size_line3 = cl3_1.number_input("Cỡ chữ Dòng 3", value=int(graphics_config["lines"][2]["initial_size"]), key="s3")
                        v_x_line3 = cl3_2.number_input("Tâm X Dòng 3", value=int(graphics_config["lines"][2]["l_x"]), key="x3")
                        v_y_line3 = cl3_3.number_input("Vị trí Y Dòng 3", value=int(graphics_config["lines"][2]["l_y"]), key="y3")
                        
                        st.markdown("🔹 **Cấu hình Dòng 4**")
                        cx4_1, cx4_2, cx4_3 = st.columns([1,1,1])
                        v_color_line4 = cx4_1.color_picker("🎨 Màu sắc:", graphics_config["lines"][3]["color"], key="c4")
                        with cx4_2: st.write(""); v_is_bold4 = st.checkbox("𝗕 In đậm (Bold)", value=graphics_config["lines"][3].get("is_bold", True), key="b4")
                        with cx4_3: st.write(""); v_is_up4 = st.checkbox("🔠 Viết hoa (UPPER)", value=graphics_config["lines"][3].get("is_uppercase", False), key="u4")
                        cl4_1, cl4_2, cl4_3 = st.columns(3)
                        v_size_line4 = cl4_1.number_input("Cỡ chữ Dòng 4", value=int(graphics_config["lines"][3]["initial_size"]), key="s4")
                        v_x_line4 = cl4_2.number_input("Tâm X Dòng 4", value=int(graphics_config["lines"][3]["l_x"]), key="x4")
                        v_y_line4 = cl4_3.number_input("Vị trí Y Dòng 4", value=int(graphics_config["lines"][3]["l_y"]), key="y4")
                        
                    st.markdown("<hr style='margin:10px 0px;'>", unsafe_allow_html=True)
                    st.markdown("#### 📋 3. Ghép Cột Dữ Liệu Tùy Biến (Smart Data Mapping):")
                    c_map = graphics_config.get("data_mapping", ["Họ và Tên", "Đơn vị", "[Thông minh] Nội dung (VĐV) - Năm sinh (HLV)", "[Thông minh] Lứa tuổi (VĐV) - Chức vụ (HLV)"])
                    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                    v_map1 = col_m1.selectbox("Dòng 1 in cột:", FIELD_OPTIONS, index=FIELD_OPTIONS.index(c_map[0]) if c_map[0] in FIELD_OPTIONS else 0, key="m1")
                    v_map2 = col_m2.selectbox("Dòng 2 in cột:", FIELD_OPTIONS, index=FIELD_OPTIONS.index(c_map[1]) if c_map[1] in FIELD_OPTIONS else 1, key="m2")
                    v_map3 = col_m3.selectbox("Dòng 3 in cột:", FIELD_OPTIONS, index=FIELD_OPTIONS.index(c_map[2]) if c_map[2] in FIELD_OPTIONS else 2, key="m3")
                    v_map4 = col_m4.selectbox("Dòng 4 in cột:", FIELD_OPTIONS, index=FIELD_OPTIONS.index(c_map[3]) if c_map[3] in FIELD_OPTIONS else 3, key="m4")
                        
                    if st.button("💾 ĐỒNG BỘ HOÀN TOÀN THAM SỐ VÀO FILE JSON", type="primary", use_container_width=True):
                        new_graphics_cfg = {
                            "font_choice": v_font_choice, "img_x": v_img_x, "img_y": v_img_y, "img_w": v_img_w, "img_h": v_img_h,
                            "w_card_cm": v_w_card_cm, "h_card_cm": v_h_card_cm, "layout_pdf": v_layout_pdf, "bg_option": v_bg_option,
                            "data_mapping": [v_map1, v_map2, v_map3, v_map4],
                            "lines": [
                                {"color": v_color_line1, "initial_size": v_size_line1, "l_x": v_x_line1, "l_y": v_y_line1, "is_bold": v_is_bold1, "is_uppercase": v_is_up1},
                                {"color": v_color_line2, "initial_size": v_size_line2, "l_x": v_x_line2, "l_y": v_y_line2, "is_bold": v_is_bold2, "is_uppercase": v_is_up2},
                                {"color": v_color_line3, "initial_size": v_size_line3, "l_x": v_x_line3, "l_y": v_y_line3, "is_bold": v_is_bold3, "is_uppercase": v_is_up3},
                                {"color": v_color_line4, "initial_size": v_size_line4, "l_x": v_x_line4, "l_y": v_y_line4, "is_bold": v_is_bold4, "is_uppercase": v_is_up4}
                            ]
                        }
                        save_graphics_config(new_graphics_cfg)
                        st.success("✅ Cấu hình đồ họa xuất bản đã được lưu trữ thành công!")
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

                # ==============================================================
                # GIAO DIỆN XEM TRƯỚC WYSIWYG
                # ==============================================================
                layout_choice = graphics_config.get("layout_pdf", "🔲 4 thẻ / 1 trang A4")
                if "4 thẻ" in layout_choice:
                    chunk_size = 4; cols_css = "repeat(2, 1fr)"; page_width = "700px" 
                    st.markdown("### 🖥️ Bản xem trước bố cục in (Lưới 4 Thẻ / Trang A4)")
                else:
                    chunk_size = 1; cols_css = "repeat(1, 1fr)"; page_width = "350px" 
                    st.markdown("### 🖥️ Bản xem trước bố cục in (1 Thẻ / Trang đơn)")
                    
                st.markdown(f"""
                <style>
                .print-preview-container {{ display: flex; flex-direction: column; align-items: center; gap: 30px; background-color: #586069; padding: 30px; border-radius: 8px; margin-top: 20px; }}
                .print-page {{ width: {page_width}; max-width: 100%; background: white; box-shadow: 0 10px 20px rgba(0,0,0,0.3); padding: 0px; display: grid; grid-template-columns: {cols_css}; gap: 0px; justify-content: center; }}
                .preview-card {{ width: 100%; height: auto; position: relative; border-right: 1px dashed #ccc; border-bottom: 1px dashed #ccc; line-height: 0; }}
                .preview-card img {{ width: 100%; height: auto; display: block; }}
                </style>
                """, unsafe_allow_html=True)
                
                html_print = '<div class="print-preview-container">'
                chunks = [print_cards[i:i + chunk_size] for i in range(0, len(print_cards), chunk_size)]
                
                for chunk in chunks:
                    html_print += '<div class="print-page">'
                    for card in chunk:
                        pil_card = draw_card_image(card, graphics_config)
                        buffered_view = io.BytesIO()
                        pil_card.save(buffered_view, format="JPEG", quality=80) 
                        b64_view = base64.b64encode(buffered_view.getvalue()).decode('utf-8')
                        html_print += f'<div class="preview-card"><img src="data:image/jpeg;base64,{b64_view}"></div>'
                    html_print += '</div>'
                html_print += '</div>'
                
                st.markdown(html_print, unsafe_allow_html=True)

                st.markdown("<br><hr>", unsafe_allow_html=True)
                with st.spinner("📦 Đang kết xuất ma trận ảnh thẻ và dàn trang PDF ReportLab..."):
                    try:
                        pdf_data_bytes = export_reportlab_pdf(print_cards, graphics_config)
                        st.download_button(
                            label=f"💾 TẢI XUỐNG FILE PDF IN ẤN HOÀN CHỈNH ({graphics_config['layout_pdf']})",
                            data=pdf_data_bytes,
                            file_name=f"file_in_the_{ma_don_vi_lam_viec}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            on_click=mark_as_printed,
                            args=(tourney_name, ma_don_vi_lam_viec)
                        )
                    except Exception as err_pdf:
                        st.error(f"❌ Lỗi biên dịch ReportLab Layout: {err_pdf}")

        else: st.error("❌ Bạn không được phân quyền truy cập chức năng in ấn.")

    # ==========================================
    # MÀN HÌNH 3: CÀI ĐẶT HỆ THỐNG (ADMIN)
    # ==========================================
    elif menu_choice == "3️⃣ Cài đặt":
        st.title("⚙️ Cài đặt Hệ thống")
        st.markdown("---")
        if role == "ADMIN":
            st.success("👑 Khu vực cấu hình phân quyền dành riêng cho Admin.")
            
            st.subheader("6. Cập nhật Dữ liệu gốc (Cơ sở dữ liệu VĐV/HLV)")
            
            if os.path.exists("data/custom_database.csv"):
                st.success("📁 **TRẠNG THÁI:** Đang sử dụng File CSV tùy chỉnh (Đã tải lên thành công).")
                if st.button("🗑️ Khôi phục CSDL gốc mặc định"):
                    os.remove("data/custom_database.csv")
                    st.cache_data.clear()
                    st.rerun()
            elif os.path.exists("data/custom_database.xlsx"):
                st.success("📁 **TRẠNG THÁI:** Đang sử dụng File Excel tùy chỉnh (Đã tải lên thành công).")
                if st.button("🗑️ Khôi phục CSDL gốc mặc định"):
                    os.remove("data/custom_database.xlsx")
                    st.cache_data.clear()
                    st.rerun()
            else:
                st.info("📁 **TRẠNG THÁI:** Đang sử dụng Dữ liệu gốc mặc định của hệ thống.")
            
            st.markdown("💡 *Hãy tải file Excel (.xlsx) hoặc (.csv) lên đây để ghi đè danh sách. File của bạn sẽ được lưu vĩnh viễn cho đến khi bạn bấm nút Khôi phục.*")
            
            with st.form("upload_db_form", clear_on_submit=True):
                uploaded_db = st.file_uploader("Tải lên CSDL mới (Yêu cầu có cột: 'Mã hội viên', 'Họ và tên', 'Năm sinh', 'Mã đơn vị', 'Đẳng cấp'...)", type=['csv', 'xlsx'])
                submit_db = st.form_submit_button("💾 Xác nhận lưu CSDL", type="primary", use_container_width=True)
                
                if submit_db and uploaded_db is not None:
                    with st.spinner("Đang lưu trữ dữ liệu vào hệ thống..."):
                        try:
                            os.makedirs("data", exist_ok=True)
                            if uploaded_db.name.endswith('.csv'):
                                with open("data/custom_database.csv", "wb") as f:
                                    f.write(uploaded_db.getbuffer())
                                if os.path.exists("data/custom_database.xlsx"):
                                    os.remove("data/custom_database.xlsx")
                            else:
                                with open("data/custom_database.xlsx", "wb") as f:
                                    f.write(uploaded_db.getbuffer())
                                if os.path.exists("data/custom_database.csv"):
                                    os.remove("data/custom_database.csv")
                            
                            st.cache_data.clear() 
                            st.rerun() 
                        except Exception as db_err:
                            st.error(f"❌ Lỗi khi lưu file: {db_err}")

            st.markdown("---")
            st.subheader("5. Quản lý Danh sách Giải đấu")
            st.info("Cài đặt thông tin giải đấu. Hệ thống tự động đổi cơ sở dữ liệu theo loại giải. Hỗ trợ bật nhiều giải song song!")
            
            cur_set = load_settings()
            tournaments = cur_set.get("tournaments", [])
            edit_t_idx = st.session_state.get('edit_tourney_idx')
            
            if edit_t_idx is not None and 0 <= edit_t_idx < len(tournaments):
                t_edit = tournaments[edit_t_idx]
                form_title = f"✏️ Đang sửa giải: {t_edit['name']}"
                def_name = t_edit['name']
                def_start = datetime.datetime.strptime(t_edit['start_date'], "%Y-%m-%d").date() if t_edit['start_date'] else datetime.date.today()
                def_end = datetime.datetime.strptime(t_edit['end_date'], "%Y-%m-%d").date() if t_edit['end_date'] else datetime.date.today()
                def_type = 0 if t_edit['type'] == "QGIA" else 1
                form_key = f"form_tourney_edit_{edit_t_idx}"
            else:
                form_title = "➕ Thêm giải đấu mới"
                def_name = ""
                def_start = datetime.date.today()
                def_end = datetime.date.today()
                def_type = 0
                form_key = "form_tourney_new"
                
            with st.form(form_key, clear_on_submit=True):
                st.markdown(f"**{form_title}**")
                c_t1, c_t2, c_t3, c_t4 = st.columns(4)
                with c_t1: new_t_start = st.date_input("1. Ngày bắt đầu", value=def_start)
                with c_t2: new_t_end = st.date_input("2. Ngày kết thúc", value=def_end)
                with c_t3: new_t_name = st.text_input("3. Tên giải đấu", value=def_name)
                with c_t4: new_t_type = st.radio("4. Loại giải", ["QGIA (Quốc Gia)", "TINH (Cấp Tỉnh)"], index=def_type)
                
                btn_label = "💾 Lưu Cập Nhật Giải" if edit_t_idx is not None else "➕ Lưu Giải Đấu Mới"
                if st.form_submit_button(btn_label, type="primary", use_container_width=True):
                    if new_t_name.strip() == "":
                        st.warning("⚠️ Vui lòng nhập Tên giải đấu!")
                    else:
                        new_t = {
                            "name": new_t_name.strip(),
                            "start_date": str(new_t_start),
                            "end_date": str(new_t_end),
                            "type": "QGIA" if "QGIA" in new_t_type else "TINH",
                            "is_active": False 
                        }
                        if edit_t_idx is not None:
                            new_t["is_active"] = tournaments[edit_t_idx].get("is_active", False)
                            tournaments[edit_t_idx] = new_t
                            st.session_state['edit_tourney_idx'] = None
                            st.success("✅ Cập nhật giải đấu thành công!")
                        else:
                            if len(tournaments) == 0: new_t["is_active"] = True
                            tournaments.append(new_t)
                            st.success("✅ Thêm giải đấu mới thành công!")
                        
                        cur_set["tournaments"] = tournaments
                        save_settings(cur_set)
                        st.rerun()
                        
            if edit_t_idx is not None:
                if st.button("❌ Hủy chỉnh sửa"):
                    st.session_state['edit_tourney_idx'] = None
                    st.rerun()

            st.markdown("#### 📌 Danh sách các giải đấu:")
            if not tournaments:
                st.warning("⚠️ Chưa có giải đấu nào được thiết lập. Vui lòng thêm mới ở trên.")
            else:
                for i, t in enumerate(tournaments):
                    is_act = t.get('is_active', False)
                    bg_color = "#e8f8f5" if is_act else "#f9f9f9"
                    border_color = "#1abc9c" if is_act else "#ddd"
                    
                    st.markdown(f"""
                    <div style="background-color: {bg_color}; border: 1px solid {border_color}; padding: 15px; border-radius: 8px; margin-bottom: 10px;">
                        <h4 style="margin: 0; color: #2c3e50;">{'⭐ (ĐANG HOẠT ĐỘNG) - ' if is_act else ''}{t['name']}</h4>
                        <p style="margin: 5px 0 0 0; font-size: 14px; color: #7f8c8d;">
                            🗓️ {t['start_date']} đến {t['end_date']} | 🎯 {'Quy mô Quốc Gia' if t['type']=='QGIA' else 'Quy mô Tỉnh/Thành'}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    c_btn1, c_btn2, c_btn3, _ = st.columns([2, 2, 2, 6])
                    with c_btn1:
                        if not is_act:
                            if st.button("✅ Bật Kích hoạt", key=f"act_{i}", use_container_width=True):
                                tournaments[i]['is_active'] = True
                                cur_set["tournaments"] = tournaments
                                save_settings(cur_set)
                                st.rerun()
                        else: 
                            if st.button("⏸️ Tắt Kích hoạt", key=f"deact_{i}", use_container_width=True):
                                tournaments[i]['is_active'] = False
                                cur_set["tournaments"] = tournaments
                                save_settings(cur_set)
                                st.rerun()
                    with c_btn2:
                        if st.button("✏️ Sửa", key=f"edit_{i}", use_container_width=True):
                            st.session_state['edit_tourney_idx'] = i
                            st.rerun()
                    with c_btn3:
                        if st.button("🗑️ Xóa", key=f"del_{i}", use_container_width=True):
                            tournaments.pop(i)
                            cur_set["tournaments"] = tournaments
                            save_settings(cur_set)
                            st.rerun()
                    st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)
                
            st.markdown("---")
            st.subheader("1. Quản lý Tài khoản Đơn vị (Gán Gmail vào Đơn vị/CLB)")
            col_sel, col_inp, col_btn = st.columns([2, 3, 1])
            with col_sel: st.selectbox("Chọn Đơn vị/CLB", danh_sach_thuc_the_cai_dat, key="map_dv_select")
            with col_inp: st.text_input("Nhập/Dán danh sách Gmail", placeholder="VD: hlv1@gmail.com, hlv2@gmail.com", key="map_email_input")
            with col_btn: st.write(""); st.button("➕ Thêm liên kết", on_click=add_map, type="primary", use_container_width=True)
                
            if st.session_state.get("thong_bao_mapping"): st.success(st.session_state.thong_bao_mapping); st.session_state.thong_bao_mapping = ""
            mapping = load_settings().get("unit_mapping", {})
            if mapping:
                for mail, dv in mapping.items():
                    cx1, cx2, cx3 = st.columns([3, 2, 1])
                    cx1.write(f"📧 `{mail}`"); cx2.markdown(f"🏢 **{dv}**"); cx3.button("🗑️ Gỡ bỏ", key=f"dm_{mail}", on_click=del_map, args=(mail,))

            st.markdown("---")
            st.subheader("2. Phân quyền chi tiết (Quyền lẻ In thẻ & Xóa)")
            cq1, cq2 = st.columns([3, 1])
            with cq1: st.text_input("Nhập Gmail cấp quyền lẻ", placeholder="VD: canbo_in@gmail.com", key="nhap_q")
            with cq2: st.write(""); st.button("➕ Thêm tài khoản lẻ", on_click=add_q, use_container_width=True)
            
            if st.session_state.get("thong_bao_quyen"): 
                if "✅" in st.session_state.thong_bao_quyen: st.success(st.session_state.thong_bao_quyen)
                else: st.error(st.session_state.thong_bao_quyen)
                st.session_state.thong_bao_quyen = ""
            
            permissions_data = load_settings().get("permissions", {})
            if permissions_data:
                for em, p in permissions_data.items():
                    cq1, cq2, cq3, cq4 = st.columns([3, 2, 2, 1])
                    cq1.write(f"📧 `{em}`")
                    cq2.checkbox("Cho phép Xóa", value=p.get("xoa_danh_sach", False), key=f"xoa_danh_sach_{em}", on_change=upd_q, args=(em, "xoa_danh_sach"))
                    cq3.checkbox("Cho phép In", value=p.get("in_the", False), key=f"in_the_{em}", on_change=upd_q, args=(em, "in_the"))
                    cq4.button("🗑️ Thu hồi", key=f"dq_{em}", on_click=del_q, args=(em,), use_container_width=True)

            st.markdown("---")
            st.subheader("3. Cài đặt Danh mục thi đấu")
            with st.form("form_danhmuc"):
                cd1, cd2 = st.columns(2)
                with cd1: k_lt = st.text_area("Lứa tuổi", value="\\n".join(settings_data.get("lua_tuoi", [])), height=150)
                with cd2: k_nd = st.text_area("Nội dung", value="\\n".join(settings_data.get("noi_dung", [])), height=150)
                if st.form_submit_button("💾 Lưu Danh Mục Giải Đấu", type="primary"):
                    cur = load_settings()
                    cur["lua_tuoi"] = [x.strip() for x in k_lt.split('\\n') if x.strip()]
                    cur["noi_dung"] = [x.strip() for x in k_nd.split('\\n') if x.strip()]
                    save_settings(cur)
                    st.success("✅ Đã cập nhật danh mục thi đấu mới thành công!")
                    st.rerun()
            
            st.markdown("---")
            st.subheader("4. Tải lên Phôi thẻ (Đồng bộ In ấn)")
            st.info("💡 Hệ thống tự động lưu phôi ngay khi bạn kéo thả file. Giao diện luôn căn bằng hoàn hảo!")
            
            c_p1, c_p2 = st.columns(2)
            with c_p1:
                st.markdown("##### 🖼️ Mẫu phôi Huấn Luyện Viên (VIP)")
                phoi_hlv_file = st.file_uploader("Thả file vào đây (Tự động lưu)", type=['png', 'jpg', 'jpeg'], key="up_hlv")
                if phoi_hlv_file is not None:
                    try:
                        img_hlv = Image.open(phoi_hlv_file)
                        img_hlv.save("phoi_hlv.png", format="PNG")
                    except Exception as e: st.error(f"Lỗi: {e}")
                if os.path.exists("phoi_hlv.png"):
                    st.image("phoi_hlv.png", caption="Phôi HLV hiện tại đang sử dụng", use_container_width=True)
                    
            with c_p2:
                st.markdown("##### 🖼️ Mẫu phôi Vận Động Viên (Thường)")
                phoi_vdv_file = st.file_uploader("Thả file vào đây (Tự động lưu)", type=['png', 'jpg', 'jpeg'], key="up_vdv")
                if phoi_vdv_file is not None:
                    try:
                        img_vdv = Image.open(phoi_vdv_file)
                        img_vdv.save("phoi_vdv.png", format="PNG")
                    except Exception as e: st.error(f"Lỗi: {e}")
                if os.path.exists("phoi_vdv.png"):
                    st.image("phoi_vdv.png", caption="Phôi VĐV hiện tại đang sử dụng", use_container_width=True)
                    
        else: st.error("❌ Bạn không có thẩm quyền cấu hình khu vực Admin.")
