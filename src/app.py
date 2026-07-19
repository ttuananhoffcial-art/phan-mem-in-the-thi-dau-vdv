import streamlit as st
import json
import os
import re
import base64
import unicodedata
import io
import datetime
import zipfile
import hashlib
import urllib.request
import time
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

# CƠ CHẾ LƯU COOKIE 24H
HAS_STX = False
try:
    import extra_streamlit_components as stx
    HAS_STX = True
except ImportError:
    pass

# ==========================================
# TỰ ĐỘNG TẢI PHÔNG CHỮ CHUẨN CHO LINUX CLOUD
# ==========================================
def download_fonts():
    try:
        if not os.path.exists("arial.ttf"):
            urllib.request.urlretrieve("https://raw.githubusercontent.com/matomo-org/travis-scripts/master/fonts/Arial.ttf", "arial.ttf")
        if not os.path.exists("arialbd.ttf"):
            urllib.request.urlretrieve("https://raw.githubusercontent.com/matomo-org/travis-scripts/master/fonts/Arial_Bold.ttf", "arialbd.ttf")
    except:
        pass
download_fonts()

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
    div[role="radiogroup"] { flex-direction: row; gap: 20px; }
    </style>
""", unsafe_allow_html=True)

CARDS_FILE = "data/submitted_cards.json"
CONFIG_GRAPHICS_FILE = "data/config_the.json"
USERS_FILE = "data/users.json"
AVATARS_DIR = "data/avatars"

ALL_ROLES = ["VĐV", "HLV", "HLV Trưởng", "Trưởng đoàn", "Trọng tài", "Ban tổ chức", "VIP", "Nhân viên", "Truyền thông"]

TEXT_CASE_OPTS = ["Viết hoa toàn bộ", "Giữ nguyên gốc", "Viết hoa chữ cái đầu mỗi chữ", "Chỉ viết hoa chữ đầu của câu"]

FIELD_OPTIONS = [
    "Họ và Tên", "Chức Vụ", "Năm sinh", "Đơn vị", "Nội dung (Hạng cân)",
    "Lứa tuổi", "Đẳng cấp", "Mã Hội Viên", "Đơn vị & Mã", "Mã Đơn vị gốc",
    "[Thông minh] Nội dung (VĐV) - Năm sinh (HLV/VIP)",
    "[Thông minh] Lứa tuổi (VĐV) - Chức vụ (HLV/VIP)", "Trống (Không in)"
]

# ==========================================
# KHỞI TẠO TRẠNG THÁI HỆ THỐNG & TÀI KHOẢN
# ==========================================
for k in ['logged_in', 'user_name', 'user_role', 'user_unit', 'can_print', 'clear_form', 'success_msg', 'success_url', 'edit_idx', 'show_settings', 'edit_tourney_idx', 'cookie_fetched']:
    if k not in st.session_state:
        st.session_state[k] = False if k in ['logged_in', 'clear_form', 'show_settings', 'can_print', 'cookie_fetched'] else (None if k in ['edit_idx', 'edit_tourney_idx'] else "")

if st.session_state['clear_form']:
    st.session_state['clear_form'] = False

def load_users():
    if not os.path.exists(USERS_FILE):
        default_admin = {
            "admin": {
                "password": "123456",
                "role": "ADMIN",
                "unit": "Tất cả",
                "can_print": True
            }
        }
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_admin, f, indent=4)
        return default_admin
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def save_users(users_data):
    with open(USERS_FILE, "w", encoding="utf-8") as f: json.dump(users_data, f, indent=4, ensure_ascii=False)

# ==============================================================
# HÀM XỬ LÝ ẢNH & THÔNG SỐ ĐỒ HỌA
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
        "data_mapping": ["Họ và Tên", "Đơn vị", "[Thông minh] Nội dung (VĐV) - Năm sinh (HLV/VIP)", "[Thông minh] Lứa tuổi (VĐV) - Chức vụ (HLV/VIP)"],
        "lines": [
            {"color": "#ff0000", "initial_size": 95, "l_x": 1243, "l_y": 1780, "text_case": 0, "is_bold": True},
            {"color": "#000000", "initial_size": 109, "l_x": 1243, "l_y": 1894, "text_case": 0, "is_bold": True},
            {"color": "#000000", "initial_size": 100, "l_x": 1243, "l_y": 2048, "text_case": 0, "is_bold": True},
            {"color": "#000000", "initial_size": 85, "l_x": 1243, "l_y": 2201, "text_case": 0, "is_bold": True}
        ]
    }
    if not os.path.exists(CONFIG_GRAPHICS_FILE):
        with open(CONFIG_GRAPHICS_FILE, "w", encoding="utf-8") as f: json.dump(default_config, f, indent=4)
    try:
        with open(CONFIG_GRAPHICS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "data_mapping" not in data: data["data_mapping"] = default_config["data_mapping"]
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
    default_data = {"lua_tuoi": [], "noi_dung": [], "tournaments": [], "printed_status": {}}
    if not os.path.exists("data/settings.json"):
        with open("data/settings.json", "w", encoding="utf-8") as f: json.dump(default_data, f)
        return default_data
    try:
        with open("data/settings.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict): return default_data
            for k in ["lua_tuoi", "noi_dung"]: 
                if k not in data or not isinstance(data[k], list): data[k] = []
            if "tournaments" not in data or not isinstance(data["tournaments"], list): data["tournaments"] = []
            if "printed_status" not in data or not isinstance(data["printed_status"], dict): data["printed_status"] = {}
            return data
    except: return default_data

def save_settings(data):
    with open("data/settings.json", "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)

def mark_as_printed(tourney, unit):
    cur = load_settings()
    if "printed_status" not in cur or not isinstance(cur["printed_status"], dict): 
        cur["printed_status"] = {}
    if tourney not in cur["printed_status"] or not isinstance(cur["printed_status"][tourney], list): 
        cur["printed_status"][tourney] = []
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

def toggle_settings(): st.session_state['show_settings'] = not st.session_state['show_settings']

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
    "VPHU": "Vĩnh Phúc", "YBAI": "Yên Bái", "CAND": "Công An Nhân Dân", "QDOI": "Quân Đội",
    "BTC": "Ban Tổ Chức Giải"
}

def get_full_unit_name(code):
    code_clean = str(code).strip().upper()
    if code_clean in UNIT_NAMES:
        return UNIT_NAMES[code_clean]
    return str(code).strip()

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
    elif field_name == "[Thông minh] Nội dung (VĐV) - Năm sinh (HLV/VIP)":
        return str(card.get("Nội dung", "")) if cv_upper in ["VĐV", "VDV"] else f"Năm sinh: {card.get('Năm sinh', '')}"
    elif field_name == "[Thông minh] Lứa tuổi (VĐV) - Chức vụ (HLV/VIP)":
        return str(card.get("Lứa tuổi", "")) if cv_upper in ["VĐV", "VDV"] else cv_full
    return ""

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
    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
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
            try:
                pdf_bytes = tao_pdf_danh_sach(danh_sach_the, ten_don_vi)
                zip_file.writestr(f"Danh_Sach_Nhan_Su_{ten_don_vi}.pdf", pdf_bytes)
            except: pass

    zip_buffer.seek(0)
    return zip_buffer.getvalue()

def draw_card_image(card, g_cfg):
    STD_W = 2480
    aspect_ratio = g_cfg["h_card_cm"] / g_cfg["w_card_cm"]
    STD_H = int(STD_W * aspect_ratio) 
    
    vip_keywords = ["HLV", "HUAN LUYEN VIEN", "TRONG TAI", "BTC", "TRUONG DOAN", "BAN TO CHUC", "THU KY", "VIP", "NHAN VIEN", "TRUYEN THONG", "Y TE", "GIAM SAT"]
    cv_goc = str(card.get("Chức vụ", "")).strip()
    if not cv_goc: cv_goc = "VĐV"
    is_vip = False
    chuc_vu_clean = remove_accents(cv_goc).upper()
    if any(kw in chuc_vu_clean for kw in vip_keywords) or cv_goc not in ["VĐV", "VDV"]:
        is_vip = True
            
    bg_choice = g_cfg.get("bg_option", "")
    base_img = Image.new("RGBA", (STD_W, STD_H), (255, 255, 255, 255))
    
    if not ("Chỉ in nội dung" in bg_choice or "Nền trắng" in bg_choice):
        phoi_path = "phoi_hlv.png" if is_vip else "phoi_vdv.png"
        if os.path.exists(phoi_path):
            try:
                img_temp = Image.open(phoi_path).convert("RGBA")
                base_img = ImageOps.fit(img_temp, (STD_W, STD_H), Image.Resampling.LANCZOS)
            except: pass
            
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
    base_font = font_family.replace(" Bold", "")
    
    font_map = {
        "Arial": {"regular": "arial.ttf", "bold": "arialbd.ttf"},
        "Times New Roman": {"regular": "times.ttf", "bold": "timesbd.ttf"},
        "Tahoma": {"regular": "tahoma.ttf", "bold": "tahomabd.ttf"},
        "Calibri": {"regular": "calibri.ttf", "bold": "calibrib.ttf"}
    }
    
    lines_text = [
        get_mapped_value(card, g_cfg["data_mapping"][0]),
        get_mapped_value(card, g_cfg["data_mapping"][1]),
        get_mapped_value(card, g_cfg["data_mapping"][2]),
        get_mapped_value(card, g_cfg["data_mapping"][3])
    ]
    
    for i, text_raw in enumerate(lines_text):
        if not text_raw: continue
        line_cfg = g_cfg["lines"][i]
        
        text_processed = text_raw.replace("HLV", "HUẤN LUYỆN VIÊN").replace("VĐV", "VẬN ĐỘNG VIÊN").replace("VDV", "VẬN ĐỘNG VIÊN")
        
        t_case = line_cfg.get("text_case", 0)
        if t_case == 0: text_processed = text_processed.upper()
        elif t_case == 2: text_processed = text_processed.title()
        elif t_case == 3: text_processed = text_processed.capitalize()
            
        hex_color = line_cfg["color"].lstrip('#')
        rgb_color = tuple(int(hex_color[j:j+2], 16) for j in (0, 2, 4))
        
        is_bold = line_cfg.get("is_bold", True)
        font_file = font_map.get(base_font, font_map["Arial"])["bold" if is_bold else "regular"]
        if not os.path.exists(font_file): 
            font_file = "arialbd.ttf" if is_bold else "arial.ttf"

        current_size = line_cfg["initial_size"]
        selected_font = None
        
        while current_size >= 20:
            try: 
                selected_font = ImageFont.truetype(font_file, current_size)
            except: 
                try:
                    selected_font = ImageFont.truetype("arial.ttf", current_size)
                except:
                    selected_font = ImageFont.load_default()
                    break
            
            bbox = draw.textbbox((0, 0), text_processed, font=selected_font)
            text_w = bbox[2] - bbox[0]
            
            # CẢI TIẾN: Bỏ ép kích thước chữ - Mở rộng tối đa tới 95% mép thẻ
            if text_w <= int(STD_W * 0.95) or selected_font == ImageFont.load_default(): break
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

# KHỞI CHẠY HỆ THỐNG CƠ BẢN
settings_data = load_settings()

danh_sach_thuc_the_cai_dat = ["BTC"] + sorted([k for k in UNIT_NAMES.keys() if k != "BTC"])

tournaments_list = settings_data.get("tournaments", [])
active_tourneys = [t for t in tournaments_list if t.get("is_active")]
tourney_name = active_tourneys[0].get("name", "") if active_tourneys else ""
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

# HỆ THỐNG AUTO-SAVE CHO MENU IN THẺ CỰC KỲ BỀN BỈ QUA CÁC LẦN F5
def get_current_graphics_config():
    return {
        "font_choice": st.session_state.cfg_font_choice,
        "img_x": st.session_state.cfg_img_x, "img_y": st.session_state.cfg_img_y,
        "img_w": st.session_state.cfg_img_w, "img_h": st.session_state.cfg_img_h,
        "w_card_cm": st.session_state.cfg_w_card_cm, "h_card_cm": st.session_state.cfg_h_card_cm,
        "layout_pdf": st.session_state.cfg_layout_pdf, "bg_option": st.session_state.cfg_bg_option,
        "data_mapping": [st.session_state.cfg_map1, st.session_state.cfg_map2, st.session_state.cfg_map3, st.session_state.cfg_map4],
        "lines": [
            {"color": st.session_state.cfg_c1, "initial_size": st.session_state.cfg_s1, "l_x": st.session_state.cfg_x1, "l_y": st.session_state.cfg_y1, "text_case": TEXT_CASE_OPTS.index(st.session_state.cfg_case1), "is_bold": st.session_state.cfg_b1},
            {"color": st.session_state.cfg_c2, "initial_size": st.session_state.cfg_s2, "l_x": st.session_state.cfg_x2, "l_y": st.session_state.cfg_y2, "text_case": TEXT_CASE_OPTS.index(st.session_state.cfg_case2), "is_bold": st.session_state.cfg_b2},
            {"color": st.session_state.cfg_c3, "initial_size": st.session_state.cfg_s3, "l_x": st.session_state.cfg_x3, "l_y": st.session_state.cfg_y3, "text_case": TEXT_CASE_OPTS.index(st.session_state.cfg_case3), "is_bold": st.session_state.cfg_b3},
            {"color": st.session_state.cfg_c4, "initial_size": st.session_state.cfg_s4, "l_x": st.session_state.cfg_x4, "l_y": st.session_state.cfg_y4, "text_case": TEXT_CASE_OPTS.index(st.session_state.cfg_case4), "is_bold": st.session_state.cfg_b4}
        ]
    }

def save_current_config():
    save_graphics_config(get_current_graphics_config())

def init_session_config():
    if 'cfg_loaded' not in st.session_state:
        g_cfg = load_graphics_config()
        
        font_list = ["Arial", "Arial Bold", "Times New Roman", "Times New Roman Bold", "Tahoma", "Tahoma Bold"]
        f_ch = g_cfg.get("font_choice", "Arial")
        st.session_state.cfg_font_choice = f_ch if f_ch in font_list else "Arial"
        
        st.session_state.cfg_img_x = int(g_cfg.get("img_x", 116))
        st.session_state.cfg_img_y = int(g_cfg.get("img_y", 1380))
        st.session_state.cfg_img_w = int(g_cfg.get("img_w", 586))
        st.session_state.cfg_img_h = int(g_cfg.get("img_h", 800))
        
        st.session_state.cfg_w_card_cm = float(g_cfg.get("w_card_cm", 10.0))
        st.session_state.cfg_h_card_cm = float(g_cfg.get("h_card_cm", 14.0))
        
        l_pdf = g_cfg.get("layout_pdf", "🔲 4 thẻ / 1 trang A4")
        st.session_state.cfg_layout_pdf = l_pdf if l_pdf in ["🔲 4 thẻ / 1 trang A4", "📄 1 thẻ / 1 trang"] else "🔲 4 thẻ / 1 trang A4"
        
        b_opt = g_cfg.get("bg_option", "🖼️ In đầy đủ")
        st.session_state.cfg_bg_option = b_opt if b_opt in ["🖼️ In đầy đủ", "⬜ Chỉ in nội dung"] else "🖼️ In đầy đủ"
        
        c_map = g_cfg.get("data_mapping", FIELD_OPTIONS[:4])
        st.session_state.cfg_map1 = c_map[0] if len(c_map)>0 and c_map[0] in FIELD_OPTIONS else FIELD_OPTIONS[0]
        st.session_state.cfg_map2 = c_map[1] if len(c_map)>1 and c_map[1] in FIELD_OPTIONS else FIELD_OPTIONS[1]
        st.session_state.cfg_map3 = c_map[2] if len(c_map)>2 and c_map[2] in FIELD_OPTIONS else FIELD_OPTIONS[2]
        st.session_state.cfg_map4 = c_map[3] if len(c_map)>3 and c_map[3] in FIELD_OPTIONS else FIELD_OPTIONS[3]
        
        for i in range(4):
            l_cfg = g_cfg["lines"][i] if i < len(g_cfg["lines"]) else {}
            st.session_state[f"cfg_c{i+1}"] = l_cfg.get("color", "#000000")
            st.session_state[f"cfg_s{i+1}"] = int(l_cfg.get("initial_size", 100))
            st.session_state[f"cfg_x{i+1}"] = int(l_cfg.get("l_x", 1243))
            st.session_state[f"cfg_y{i+1}"] = int(l_cfg.get("l_y", 1800 + i*100))
            t_case_idx = l_cfg.get("text_case", 0)
            st.session_state[f"cfg_case{i+1}"] = TEXT_CASE_OPTS[t_case_idx] if 0 <= t_case_idx < len(TEXT_CASE_OPTS) else TEXT_CASE_OPTS[0]
            st.session_state[f"cfg_b{i+1}"] = l_cfg.get("is_bold", True)
        
        st.session_state.cfg_loaded = True

# KHỞI TRÌNH QUẢN LÝ COOKIE (24H LOGIN) - FIX LỖI BẮT ĐĂNG NHẬP LẠI
cookie_manager = None
if HAS_STX:
    cookie_manager = stx.CookieManager(key="auth_cm")
    
    if not st.session_state['cookie_fetched']:
        st.session_state['cookie_fetched'] = True
        time.sleep(0.3)
        st.rerun()

    if not st.session_state['logged_in']:
        auth_token = cookie_manager.get("tk_auth_24h")
        if auth_token and isinstance(auth_token, str):
            try:
                uname, hpwd = auth_token.split("||")
                users_db = load_users()
                if uname in users_db and users_db[uname]["password"] == hpwd:
                    st.session_state['logged_in'] = True
                    st.session_state['user_name'] = uname
                    st.session_state['user_role'] = users_db[uname]["role"]
                    st.session_state['user_unit'] = users_db[uname]["unit"]
                    st.session_state['can_print'] = users_db[uname].get("can_print", False)
                    st.rerun()
            except:
                pass

# ==========================================
# HỆ THỐNG ĐĂNG NHẬP CHÍNH
# ==========================================
if not st.session_state['logged_in']:
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center; color: #2980b9;'>🔐 HỆ THỐNG QUẢN LÝ THẺ TAEKWONDO</h2>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username_input = st.text_input("Tên đăng nhập")
            password_input = st.text_input("Mật khẩu", type="password")
            submit_login = st.form_submit_button("Đăng nhập Hệ Thống", type="primary", use_container_width=True)
            
            if submit_login:
                users_db = load_users()
                uname = username_input.strip()
                if uname in users_db:
                    stored_pwd = users_db[uname].get("password", "")
                    
                    if stored_pwd == password_input:
                        st.session_state['logged_in'] = True
                        st.session_state['user_name'] = uname
                        st.session_state['user_role'] = users_db[uname]["role"]
                        st.session_state['user_unit'] = users_db[uname]["unit"]
                        st.session_state['can_print'] = users_db[uname].get("can_print", False)
                        
                        if HAS_STX and cookie_manager is not None:
                            expire_time = datetime.datetime.now() + datetime.timedelta(days=1)
                            cookie_manager.set("tk_auth_24h", f"{uname}||{stored_pwd}", expires_at=expire_time)
                            time.sleep(0.3)
                            
                        st.success("Đăng nhập thành công!")
                        st.rerun()
                    else:
                        st.error("❌ Tên đăng nhập hoặc mật khẩu không chính xác!")
                else:
                    st.error("❌ Tên đăng nhập hoặc mật khẩu không chính xác!")
else:
    # ĐÃ ĐĂNG NHẬP THÀNH CÔNG
    st.sidebar.success("✅ Đăng nhập thành công!")
    st.sidebar.markdown(f"👤 **Tài khoản:** {st.session_state['user_name']}")
    st.sidebar.markdown("---")

    role = st.session_state['user_role']
    quyen_in = st.session_state['can_print']
    ma_don_vi_lam_viec = ""

    menu_options = ["1️⃣ Nộp Danh Sách Làm Thẻ", "2️⃣ In Thẻ"]
    if role == "ADMIN":
        menu_options.append("3️⃣ Cài đặt (Admin)")
    menu_options.append("4️⃣ Đổi Mật Khẩu")

    menu_choice = st.sidebar.radio("📌 CHỨC NĂNG CHÍNH", menu_options)
    st.sidebar.markdown("---")

    all_cards_for_filter = load_submitted_cards()
    submitted_units_set = set()
    for c in all_cards_for_filter:
        dv_str = str(c.get("Đơn_vị", "")).strip()
        if dv_str: submitted_units_set.add(dv_str)
    submitted_units = sorted(list(submitted_units_set))

    if role == "ADMIN":
        st.sidebar.info("👑 Quyền: QUẢN TRỊ VIÊN")
        
        all_admin_units = sorted(list(set(submitted_units + danh_sach_thuc_the_cai_dat)))
        if "BTC" in all_admin_units:
            all_admin_units.remove("BTC")
            all_admin_units = ["BTC"] + all_admin_units
            
        printed_status = settings_data.get("printed_status", {})
        printed_units = printed_status.get(tourney_name, [])
        
        def format_dv(dv):
            if dv == "-- Chọn --": return dv
            if dv in printed_units: return f"🟢 [Đã in] {dv}"
            if dv in submitted_units: return f"🔴 [Đã nộp] {dv}"
            return f"⚪ [Trống] {dv}"
            
        don_vi_chon = st.sidebar.selectbox("📌 Chọn Đơn vị (Quản lý / Nộp hộ):", ["-- Chọn --"] + all_admin_units, format_func=format_dv)
        custom_dv_admin = st.sidebar.text_input("✍️ Hoặc gõ tên CLB mới (nếu chưa có):", placeholder="Ví dụ: CLB Quận 1")
        
        if custom_dv_admin.strip():
            ma_don_vi_lam_viec = custom_dv_admin.strip()
        elif don_vi_chon != "-- Chọn --":
            ma_don_vi_lam_viec = don_vi_chon
            
    elif role == "DON_VI":
        ma_don_vi_lam_viec = st.session_state['user_unit']
        st.sidebar.info(f"🏢 Đơn vị: {ma_don_vi_lam_viec}")
        
    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 LÀM MỚI TẢI LẠI DỮ LIỆU", type="primary", use_container_width=True): st.cache_data.clear(); st.rerun()
    if st.sidebar.button("Đăng xuất", use_container_width=True): 
        if HAS_STX and cookie_manager is not None: 
            cookie_manager.delete("tk_auth_24h")
            time.sleep(0.2)
        st.session_state.clear(); st.cache_data.clear(); st.rerun()

    # ==========================================
    # MÀN HÌNH 1: NỘP DANH SÁCH LÀM THẺ 
    # ==========================================
    if menu_choice == "1️⃣ Nộp Danh Sách Làm Thẻ":
        st.title("📑 Nộp Danh Sách Làm Thẻ")
        
        if not active_tourneys:
            st.error("🚨 Không có giải đấu nào đang mở! Vui lòng nhờ Admin vào phần Cài Đặt -> Kích hoạt ít nhất 1 Giải đấu.")
        else:
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
            st.session_state['success_msg'] = ""

        all_cards = load_submitted_cards()
        
        if st.session_state['edit_idx'] is not None:
            edit_i = st.session_state['edit_idx']
            if 0 <= edit_i < len(all_cards):
                if not is_registration_open and role != "ADMIN":
                    st.error(f"🚨 {date_err_msg}")
                    if st.button("🔙 Quay lại danh sách"):
                        st.session_state['edit_idx'] = None
                        st.rerun()
                else:
                    card_edit = all_cards[edit_i]
                    st.markdown("---")
                    st.markdown(f"<h3 style='color: #e67e22;'>✏️ Đang chỉnh sửa thẻ: {card_edit.get('Họ tên','')} - {card_edit.get('Mã','')}</h3>", unsafe_allow_html=True)
                    
                    c_e1, c_e2, c_e3 = st.columns([2, 2, 2])
                    list_luatuoi = list(dict.fromkeys(["-- Chọn lứa tuổi --", "Không"] + settings_data.get("lua_tuoi", [])))
                    list_noidung = list(dict.fromkeys(["-- Chọn nội dung --", "Không"] + settings_data.get("noi_dung", [])))
                    
                    with c_e1:
                        edit_ht = st.text_input("Họ và tên", value=card_edit.get("Họ tên", ""))
                        
                        can_custom_role = (role == "ADMIN" or ma_don_vi_lam_viec.upper() == "BTC")
                        role_options = ALL_ROLES.copy()
                        if can_custom_role:
                            role_options.append("Khác (Nhập tay)")
                            
                        current_cv = card_edit.get("Chức vụ", "VĐV")
                        if current_cv not in ALL_ROLES:
                            role_options.insert(0, current_cv)
                            idx_cv = 0
                        else:
                            idx_cv = role_options.index(current_cv)
                            
                        edit_cv = st.selectbox("Chức vụ đoàn", role_options, index=idx_cv)
                        if edit_cv == "Khác (Nhập tay)" or (edit_cv not in ALL_ROLES and can_custom_role):
                            val = edit_cv if edit_cv != "Khác (Nhập tay)" else ""
                            edit_cv_final = st.text_input("✍️ Chức vụ thực tế in trên thẻ:", value=val)
                        else:
                            edit_cv_final = edit_cv
                            
                        edit_dc = st.text_input("Cấp / Đẳng", value=card_edit.get("Đẳng cấp", ""))
                        
                    with c_e2:
                        edit_ns = st.text_input("Năm sinh", value=card_edit.get("Năm sinh", ""))
                        edit_lt = st.selectbox("Lứa tuổi thi đấu", list_luatuoi, index=list_luatuoi.index(card_edit.get("Lứa tuổi","Không")) if card_edit.get("Lứa tuổi","Không") in list_luatuoi else 0)
                        edit_nd = st.selectbox("Nội dung thi đấu", list_noidung, index=list_noidung.index(card_edit.get("Nội dung","Không")) if card_edit.get("Nội dung","Không") in list_noidung else 0)
                    with c_e3:
                        new_file = st.file_uploader("Thay ảnh chân dung mới", type=['png', 'jpg', 'jpeg'])
                        
                    if st.button("💾 Lưu cập nhật", type="primary"):
                        all_cards[edit_i]["Họ tên"] = edit_ht
                        all_cards[edit_i]["Chức vụ"] = edit_cv_final.strip() if edit_cv_final.strip() else "VĐV"
                        all_cards[edit_i]["Lứa tuổi"] = edit_lt
                        all_cards[edit_i]["Nội dung"] = edit_nd
                        all_cards[edit_i]["Đẳng cấp"] = edit_dc
                        all_cards[edit_i]["Năm sinh"] = edit_ns
                        if new_file is not None:
                            old_path = all_cards[edit_i].get("Ảnh_Path", "")
                            if old_path and os.path.exists(old_path):
                                try: os.remove(old_path)
                                except: pass
                            all_cards[edit_i]["Ảnh_Path"] = process_and_save_image(new_file, all_cards[edit_i].get("Mã", "NoID"))
                            if "Ảnh_Base64" in all_cards[edit_i]: del all_cards[edit_i]["Ảnh_Base64"]
                        with open(CARDS_FILE, "w", encoding="utf-8") as f: json.dump(all_cards, f, ensure_ascii=False)
                        st.session_state.update({'edit_idx': None, 'success_msg': "✅ Cập nhật hồ sơ thành công!"}); st.rerun()

        if not ma_don_vi_lam_viec:
            if role == "ADMIN":
                st.warning("⚠️ Chọn hoặc nhập Đơn vị ở menu bên trái để nộp hồ sơ & xem danh sách.")
            else:
                st.warning("⚠️ Vui lòng liên hệ Admin để gán tài khoản vào Đơn vị!")
        elif st.session_state['edit_idx'] is None:
            st.markdown("### 📝 Nhập thông tin đăng ký làm thẻ mới")
            
            if not is_registration_open and role != "ADMIN":
                st.error(f"🚨 {date_err_msg}")
            else:
                if role == "ADMIN" and not is_registration_open:
                    st.warning(f"⚠️ {date_err_msg} (Admin đang được ưu tiên nộp quá hạn!)")
                    
                with st.container():
                    c1, c2 = st.columns(2)
                    with c1:
                        input_ho_ten = st.text_input("Họ và Tên (*)")
                        input_ma_hv = st.text_input("Mã Định Danh/Thẻ (*)")
                        
                        can_custom_role = (role == "ADMIN" or ma_don_vi_lam_viec.upper() == "BTC")
                        role_options = ALL_ROLES.copy()
                        if can_custom_role:
                            role_options.append("Khác (Nhập tay)")
                            
                        cv_chon = st.selectbox("📌 Chức vụ", role_options)
                        if cv_chon == "Khác (Nhập tay)":
                            cv_final = st.text_input("✍️ Nhập chức vụ khác (In trên thẻ):")
                        else:
                            cv_final = cv_chon
                            
                        ns_chon = st.text_input("Năm sinh (VD: 2005)")
                    with c2:
                        dc_chon = st.text_input("Cấp / Đẳng")
                        lt_chon = st.selectbox("Lứa tuổi", ["-- Chọn lứa tuổi --"] + settings_data.get("lua_tuoi", []))
                        nd_chon = st.selectbox("Nội dung tranh tài", ["-- Chọn nội dung --"] + settings_data.get("noi_dung", []))
                        uploaded_file = st.file_uploader("Tải lên ảnh thẻ (*)", type=['png', 'jpg', 'jpeg'])
                        
                    if st.button("💾 Ghi nhận hồ sơ", type="primary"):
                        if not input_ho_ten.strip() or not input_ma_hv.strip() or uploaded_file is None or not cv_final.strip():
                            st.error("⚠️ Vui lòng điền đầy đủ Họ Tên, Mã số, Chức vụ và tải lên Ảnh thẻ!")
                        else:
                            img_path = process_and_save_image(uploaded_file, input_ma_hv)
                            save_submitted_card({
                                "Người_nộp": st.session_state['user_name'], 
                                "Đơn_vị": ma_don_vi_lam_viec, 
                                "Đơn_vị_gốc": ma_don_vi_lam_viec,
                                "Mã": input_ma_hv, 
                                "Chức vụ": cv_final.strip(), 
                                "Họ tên": input_ho_ten.strip(),
                                "Năm sinh": ns_chon.strip(), 
                                "Nội dung": nd_chon, 
                                "Lứa tuổi": lt_chon, 
                                "Đẳng cấp": dc_chon.strip(),
                                "Ảnh_Path": img_path
                            })
                            st.session_state.update({'success_msg': "✅ Đã ghi nhận hồ sơ mới!", 'clear_form': True})
                            st.rerun()

        if ma_don_vi_lam_viec and st.session_state['edit_idx'] is None:
            all_cards_updated = load_submitted_cards()
            display_cards = []
            
            for c in all_cards_updated:
                dv = str(c.get("Đơn_vị", "")).strip()
                is_my_unit = (ma_don_vi_lam_viec and ma_don_vi_lam_viec != "-- Chọn --" and dv.upper() == ma_don_vi_lam_viec.upper())
                is_btc_viewing_vips = (ma_don_vi_lam_viec.upper() == "BTC" and c.get("Chức vụ") in ["Trọng tài", "Ban tổ chức", "VIP", "Nhân viên", "Truyền thông"])
                
                if is_my_unit or is_btc_viewing_vips:
                    display_cards.append(c)
            
            if display_cards:
                st.markdown("<br><hr>", unsafe_allow_html=True)
                c_header, c_export, c_del = st.columns([2, 1, 1])
                with c_header: 
                    st.subheader(f"🖼️ Danh sách thẻ ({len(display_cards)} nhân sự)")
                
                with c_export:
                    try:
                        zip_data_export = tao_file_zip_xuat_du_lieu(display_cards, ma_don_vi_lam_viec)
                        st.download_button(
                            label="📥 TẢI BÁO CÁO PDF & ẢNH (.ZIP)",
                            data=zip_data_export,
                            file_name=f"Ho_So_{ma_don_vi_lam_viec}.zip",
                            mime="application/zip",
                            use_container_width=True
                        )
                    except Exception as zip_err:
                        st.warning("Đang xử lý dữ liệu in ấn, vui lòng đợi vài giây và F5 lại trang...")

                if role == "ADMIN" and ma_don_vi_lam_viec:
                    with c_del:
                        if st.button(f"🚨 XÓA TẤT CẢ", type="primary", use_container_width=True):
                            with st.spinner("Đang dọn dẹp dữ liệu..."):
                                all_remaining = []
                                deleted_count = 0
                                for c in all_cards_updated:
                                    dv_xoa = str(c.get("Đơn_vị")).strip().upper()
                                    if dv_xoa == ma_don_vi_lam_viec.upper(): 
                                        img_path = c.get('Ảnh_Path', '')
                                        if img_path and os.path.exists(img_path):
                                            try: os.remove(img_path)
                                            except: pass
                                        deleted_count += 1
                                    else: all_remaining.append(c)
                                with open(CARDS_FILE, "w", encoding="utf-8") as f:
                                    json.dump(all_remaining, f, ensure_ascii=False)
                                
                                st.session_state['success_msg'] = f"✅ Đã xóa sạch {deleted_count} thẻ của đơn vị!"
                                st.rerun()
                                
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

                standard_roles = ["VIP", "Ban tổ chức", "Trọng tài", "Truyền thông", "Nhân viên", "Trưởng đoàn", "HLV Trưởng", "HLV", "VĐV"]
                all_present_roles = []
                for c in paged_cards:
                    r = c.get("Chức vụ", "VĐV")
                    if r not in all_present_roles:
                        all_present_roles.append(r)
                        
                display_roles = [r for r in standard_roles if r in all_present_roles]
                other_roles = [r for r in all_present_roles if r not in standard_roles]
                display_roles.extend(other_roles)

                for ten_cv in display_roles:
                    nhom = [(i, c) for i, c in enumerate(all_cards_updated) if c in paged_cards and c.get("Chức vụ") == ten_cv]
                    if nhom:
                        st.markdown(f"#### 📌 Chức vụ: {ten_cv} ({len(nhom)})")
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
                                html_content += f'<div class="card-text">🎂 NS: {card.get("Năm sinh", "")}</div>'
                                if str(card.get('Đẳng cấp', '')).strip():
                                    html_content += f'<div class="card-text">🥋 Đẳng: {card.get("Đẳng cấp", "")}</div>'
                                if card.get("Chức vụ") == "VĐV":
                                    html_content += f'<div class="card-text" style="color: #0984e3; font-weight: bold;">🥋 {card.get("Nội dung", "")}</div>'
                                    html_content += f'<div class="card-text" style="color: #e17055; font-weight: bold;">🏅 {card.get("Lứa tuổi", "")}</div>'
                                html_content += f'<div class="card-footer">👤 Nộp bởi: {card.get("Người_nộp", "")}</div></div>'
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
    # 🖨️ MÀN HÌNH 2: IN THẺ (GIAO DIỆN MỚI TỰ ĐỘNG LƯU)
    # ==============================================================
    elif menu_choice == "2️⃣ In Thẻ":
        if not ma_don_vi_lam_viec: 
            st.warning(f"⚠️ Vui lòng chọn Đơn vị ở Menu bên trái để tải danh sách thẻ!")
        elif role == "ADMIN" or quyen_in: 
            all_cards = load_submitted_cards()
            
            print_cards = []
            for c in all_cards:
                dv = str(c.get("Đơn_vị", "")).strip()
                is_my_unit = (dv.upper() == ma_don_vi_lam_viec.upper())
                is_btc_viewing_vips = (ma_don_vi_lam_viec.upper() == "BTC" and c.get("Chức vụ") in ["Trọng tài", "Ban tổ chức", "VIP", "Nhân viên", "Truyền thông"])
                
                if is_my_unit or is_btc_viewing_vips:
                    print_cards.append(c)
            
            if len(print_cards) == 0:
                st.warning(f"Đơn vị {ma_don_vi_lam_viec} hiện chưa có dữ liệu in thẻ.")
            else:
                st.success(f"Tìm thấy {len(print_cards)} thẻ sẵn sàng. Bảng cấu hình tự động lưu bên dưới.")
                
                init_session_config()
                
                font_list = ["Arial", "Arial Bold", "Times New Roman", "Times New Roman Bold", "Tahoma", "Tahoma Bold"]
                st.selectbox("🔤 Chọn kiểu phông chữ:", font_list, key="cfg_font_choice", on_change=save_current_config)
                
                with st.expander("🔧 Bấm vào đây để KÉO ẢNH & ĐỔI MÀU/KIỂU CHỮ (Tự động lưu)", expanded=True):
                    tab_photo, tab_l12, tab_l34 = st.tabs(["📷 Ảnh chân dung", "🔤 Dòng 1 & Dòng 2", "🔤 Dòng 3 & Dòng 4"])
                    
                    with tab_photo:
                        col_img1, col_img2 = st.columns(2)
                        col_img1.number_input("Vị trí ngang X (Ảnh)", key="cfg_img_x", on_change=save_current_config)
                        col_img2.number_input("Vị trí dọc Y (Ảnh)", key="cfg_img_y", on_change=save_current_config)
                        col_img1.number_input("Chiều rộng khung ảnh (img_w)", key="cfg_img_w", on_change=save_current_config)
                        col_img2.number_input("Chiều cao khung ảnh (img_h)", key="cfg_img_h", on_change=save_current_config)
                    
                    with tab_l12:
                        st.markdown("🔹 **Cấu hình Dòng 1**")
                        col_c1, col_k1 = st.columns([1.5, 4])
                        with col_c1:
                            cc1, cb1 = st.columns(2)
                            cc1.color_picker("🎨 Màu:", key="cfg_c1", on_change=save_current_config)
                            with cb1:
                                st.write("")
                                st.checkbox("𝗕 In đậm", key="cfg_b1", on_change=save_current_config)
                        col_k1.radio("Kiểu chữ Dòng 1:", TEXT_CASE_OPTS, horizontal=True, key="cfg_case1", on_change=save_current_config)
                        
                        cl1_1, cl1_2, cl1_3 = st.columns(3)
                        cl1_1.number_input("Cỡ chữ Dòng 1", key="cfg_s1", on_change=save_current_config)
                        cl1_2.number_input("Tâm X Dòng 1", key="cfg_x1", on_change=save_current_config)
                        cl1_3.number_input("Vị trí Y Dòng 1", key="cfg_y1", on_change=save_current_config)
                        
                        st.markdown("<hr style='margin:5px 0px;'>", unsafe_allow_html=True)
                        st.markdown("🔹 **Cấu hình Dòng 2**")
                        col_c2, col_k2 = st.columns([1.5, 4])
                        with col_c2:
                            cc2, cb2 = st.columns(2)
                            cc2.color_picker("🎨 Màu:", key="cfg_c2", on_change=save_current_config)
                            with cb2:
                                st.write("")
                                st.checkbox("𝗕 In đậm", key="cfg_b2", on_change=save_current_config)
                        col_k2.radio("Kiểu chữ Dòng 2:", TEXT_CASE_OPTS, horizontal=True, key="cfg_case2", on_change=save_current_config)
                        
                        cl2_1, cl2_2, cl2_3 = st.columns(3)
                        cl2_1.number_input("Cỡ chữ Dòng 2", key="cfg_s2", on_change=save_current_config)
                        cl2_2.number_input("Tâm X Dòng 2", key="cfg_x2", on_change=save_current_config)
                        cl2_3.number_input("Vị trí Y Dòng 2", key="cfg_y2", on_change=save_current_config)
                        
                    with tab_l34:
                        st.markdown("🔹 **Cấu hình Dòng 3**")
                        col_c3, col_k3 = st.columns([1.5, 4])
                        with col_c3:
                            cc3, cb3 = st.columns(2)
                            cc3.color_picker("🎨 Màu:", key="cfg_c3", on_change=save_current_config)
                            with cb3:
                                st.write("")
                                st.checkbox("𝗕 In đậm", key="cfg_b3", on_change=save_current_config)
                        col_k3.radio("Kiểu chữ Dòng 3:", TEXT_CASE_OPTS, horizontal=True, key="cfg_case3", on_change=save_current_config)
                        
                        cl3_1, cl3_2, cl3_3 = st.columns(3)
                        cl3_1.number_input("Cỡ chữ Dòng 3", key="cfg_s3", on_change=save_current_config)
                        cl3_2.number_input("Tâm X Dòng 3", key="cfg_x3", on_change=save_current_config)
                        cl3_3.number_input("Vị trí Y Dòng 3", key="cfg_y3", on_change=save_current_config)
                        
                        st.markdown("<hr style='margin:5px 0px;'>", unsafe_allow_html=True)
                        st.markdown("🔹 **Cấu hình Dòng 4**")
                        col_c4, col_k4 = st.columns([1.5, 4])
                        with col_c4:
                            cc4, cb4 = st.columns(2)
                            cc4.color_picker("🎨 Màu:", key="cfg_c4", on_change=save_current_config)
                            with cb4:
                                st.write("")
                                st.checkbox("𝗕 In đậm", key="cfg_b4", on_change=save_current_config)
                        col_k4.radio("Kiểu chữ Dòng 4:", TEXT_CASE_OPTS, horizontal=True, key="cfg_case4", on_change=save_current_config)
                        
                        cl4_1, cl4_2, cl4_3 = st.columns(3)
                        cl4_1.number_input("Cỡ chữ Dòng 4", key="cfg_s4", on_change=save_current_config)
                        cl4_2.number_input("Tâm X Dòng 4", key="cfg_x4", on_change=save_current_config)
                        cl4_3.number_input("Vị trí Y Dòng 4", key="cfg_y4", on_change=save_current_config)

                with st.container():
                    st.markdown("#### 📐 A. Kích thước & Bố cục PDF")
                    col_k1, col_k2, col_k3, col_k4 = st.columns(4)
                    col_k1.number_input("Rộng thẻ (cm):", step=0.10, key="cfg_w_card_cm", on_change=save_current_config)
                    col_k2.number_input("Cao thẻ (cm):", step=0.10, key="cfg_h_card_cm", on_change=save_current_config)
                    col_k3.radio("Dàn trang PDF:", ["🔲 4 thẻ / 1 trang A4", "📄 1 thẻ / 1 trang"], key="cfg_layout_pdf", on_change=save_current_config)
                    col_k4.radio("Nền phôi:", ["🖼️ In đầy đủ", "⬜ Chỉ in nội dung"], key="cfg_bg_option", on_change=save_current_config)

                st.markdown("#### 📋 B. Ghép Cột Dữ Liệu Tùy Biến:")
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                col_m1.selectbox("Dòng 1 in:", FIELD_OPTIONS, key="cfg_map1", on_change=save_current_config)
                col_m2.selectbox("Dòng 2 in:", FIELD_OPTIONS, key="cfg_map2", on_change=save_current_config)
                col_m3.selectbox("Dòng 3 in:", FIELD_OPTIONS, key="cfg_map3", on_change=save_current_config)
                col_m4.selectbox("Dòng 4 in:", FIELD_OPTIONS, key="cfg_map4", on_change=save_current_config)

                # Lấy config hiện tại để hiển thị xem trước
                graphics_config = get_current_graphics_config()

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
    elif menu_choice == "3️⃣ Cài đặt (Admin)":
        st.title("⚙️ Cài đặt Hệ thống")
        st.markdown("---")
        
        st.subheader("1. Quản lý Danh sách Giải đấu")
        st.info("Cài đặt thông tin giải đấu. Hệ thống hỗ trợ bật/tắt để mở/đóng cổng đăng ký.")
        
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
        st.subheader("2. Quản lý Tài Khoản Người Dùng (HLV/Đơn vị)")
        
        users_db = load_users()
        
        with st.form("create_user_form"):
            st.markdown("**➕ Tạo tài khoản mới cho HLV/Đơn vị**")
            c1, c2, c3, c4 = st.columns(4)
            with c1: new_u = st.text_input("Tên đăng nhập (Viết liền, không dấu)")
            with c2: new_p = st.text_input("Mật khẩu")
            with c3: new_dv_chon = st.selectbox("Chọn Tỉnh/Thành/BTC", ["-- Chọn --"] + danh_sach_thuc_the_cai_dat)
            with c4: new_dv_custom = st.text_input("Hoặc nhập tên CLB mới")
            
            c_print = st.checkbox("🖨️ Cho phép tài khoản này tự In thẻ", value=False)
            
            if st.form_submit_button("Tạo Tài Khoản", type="primary"):
                new_u = new_u.strip()
                final_dv = new_dv_custom.strip() if new_dv_custom.strip() else new_dv_chon
                
                if not new_u or not new_p:
                    st.warning("⚠️ Vui lòng nhập đủ tên đăng nhập và mật khẩu!")
                elif final_dv == "-- Chọn --":
                    st.warning("⚠️ Vui lòng chọn Tỉnh/Thành hoặc nhập tên CLB mới!")
                elif new_u in users_db:
                    st.error(f"❌ Tài khoản '{new_u}' đã tồn tại!")
                else:
                    users_db[new_u] = {
                        "password": new_p,
                        "role": "DON_VI",
                        "unit": final_dv,
                        "can_print": c_print
                    }
                    save_users(users_db)
                    st.success(f"✅ Đã tạo tài khoản '{new_u}' cho đơn vị '{final_dv}' thành công!")
                    st.rerun()

        st.markdown("**📋 Danh sách tài khoản hiện tại:**")
        for u, info in users_db.items():
            if u == "admin": continue
            c1, c2, c3, c4, c5, c6 = st.columns([1.5, 1.5, 2, 1.5, 1.5, 1])
            c1.write(f"👤 **{u}**")
            
            pwd_display = info.get('password', '')
            if len(pwd_display) == 64: 
                pwd_display = "(Đã mã hóa cũ)"
                
            c2.write(f"🔑 MK: `{pwd_display}`")
            c3.write(f"🏢 {info.get('unit', '')}")
            c4.write(f"🛡️ {info.get('role', '')}")
            c5.write("🖨️ In: " + ("Có" if info.get('can_print', False) else "Không"))
            if c6.button("🗑️ Xóa", key=f"del_user_{u}"):
                del users_db[u]
                save_users(users_db)
                st.rerun()

        st.markdown("---")
        st.subheader("3. Cài đặt Danh mục Lứa tuổi / Nội dung")
        with st.form("form_danhmuc"):
            cd1, cd2 = st.columns(2)
            with cd1: k_lt = st.text_area("Lứa tuổi", value="\n".join(settings_data.get("lua_tuoi", [])), height=150)
            with cd2: k_nd = st.text_area("Nội dung", value="\n".join(settings_data.get("noi_dung", [])), height=150)
            if st.form_submit_button("💾 Lưu Danh Mục Giải Đấu", type="primary"):
                cur = load_settings()
                cur["lua_tuoi"] = [x.strip() for x in k_lt.split('\n') if x.strip()]
                cur["noi_dung"] = [x.strip() for x in k_nd.split('\n') if x.strip()]
                save_settings(cur)
                st.success("✅ Đã cập nhật danh mục thi đấu mới thành công!")
                st.rerun()
        
        st.markdown("---")
        st.subheader("4. Tải lên Phôi thẻ (Đồng bộ In ấn)")
        st.info("💡 Hệ thống tự động lưu phôi ngay khi bạn kéo thả file. Giao diện luôn căn bằng hoàn hảo!")
        
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            st.markdown("##### 🖼️ Mẫu phôi VIP (Dành cho Trọng tài, BTC, HLV, Truyền thông...)")
            phoi_hlv_file = st.file_uploader("Thả file vào đây (Tự động lưu)", type=['png', 'jpg', 'jpeg'], key="up_hlv")
            if phoi_hlv_file is not None:
                try:
                    img_hlv = Image.open(phoi_hlv_file)
                    img_hlv.save("phoi_hlv.png", format="PNG")
                except Exception as e: st.error(f"Lỗi: {e}")
            if os.path.exists("phoi_hlv.png"):
                st.image("phoi_hlv.png", caption="Phôi VIP hiện tại đang sử dụng", use_container_width=True)
                
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

    # ==========================================
    # MÀN HÌNH 4: ĐỔI MẬT KHẨU
    # ==========================================
    elif menu_choice == "4️⃣ Đổi Mật Khẩu":
        st.title("🔑 Đổi Mật Khẩu")
        st.markdown("---")
        
        with st.form("change_pwd_form"):
            old_pwd = st.text_input("Mật khẩu cũ", type="password")
            new_pwd = st.text_input("Mật khẩu mới", type="password")
            confirm_pwd = st.text_input("Xác nhận mật khẩu mới", type="password")
            
            if st.form_submit_button("💾 Lưu Mật Khẩu Đổi Mới", type="primary"):
                users_db = load_users()
                uname = st.session_state['user_name']
                
                stored_pwd = users_db[uname]["password"]
                
                if stored_pwd != old_pwd:
                    st.error("❌ Mật khẩu cũ không chính xác!")
                elif new_pwd != confirm_pwd:
                    st.error("❌ Mật khẩu mới không khớp với xác nhận!")
                elif len(new_pwd) < 6:
                    st.error("❌ Mật khẩu phải có ít nhất 6 ký tự!")
                else:
                    users_db[uname]["password"] = new_pwd
                    save_users(users_db)
                    st.success("✅ Đổi mật khẩu thành công! Bạn có thể sử dụng mật khẩu mới trong lần đăng nhập tiếp theo.")
