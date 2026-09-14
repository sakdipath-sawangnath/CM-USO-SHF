import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

# ==========================================
# 1. การตั้งค่าระบบและฐานข้อมูล (Database Setup)
# ==========================================
DB_FILE = "cm_management.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS cm_cases (
            case_id TEXT PRIMARY KEY,
            station_name TEXT,
            province TEXT,
            reporter_name TEXT,
            reporter_phone TEXT,
            issue_desc TEXT,
            equipment_type TEXT,
            sla_category TEXT,
            report_time TEXT,
            sla_deadline TEXT,
            status TEXT,
            technician_name TEXT,
            solution_desc TEXT,
            original_sn TEXT,
            new_sn TEXT,
            is_spare_used INTEGER,
            spare_sn TEXT,
            spare_install_date TEXT,
            spare_return_deadline TEXT,
            completion_time TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 2. ฟังก์ชันคำนวณ SLA ตามเงื่อนไข TOR
# ==========================================
def get_sla_info(equipment):
    sla_3h = [
        "ระบบศูนย์ควบคุมสถานีแม่ข่าย (BSSC)",
        "ชุดสั่งการ (Dispatcher Console)",
        "ระบบบริหารจัดการ SD-WAN Controller"
    ]
    sla_3d = [
        "ชุดอุปกรณ์ทวนสัญญาณผ่านคลื่นความถี่สูง (SHF)",
        "ชุดอุปกรณ์ Gateway เชื่อมต่อ Analog",
        "สถานีแม่ข่ายแบบ 1 Carrier (Outdoor)",
        "อุปกรณ์กระจายสัญญาณ L3 Switch (24 Ports)",
        "เครื่องสำรองไฟฟ้า ขนาด 3 kVA"
    ]
    sla_4d = [
        "เครื่องวิทยุลูกข่ายชนิดมือถือ",
        "เครื่องวิทยุลูกข่ายชนิดประจำที่ ณ ที่ทำการหมู่บ้าน"
    ]
    
    if equipment in sla_3h:
        return 3, "3 ชั่วโมง (ด่วนที่สุด)"
    elif equipment in sla_3d:
        return 72, "3 วัน"
    elif equipment in sla_4d:
        return 96, "4 วัน"
    return 72, "3 วัน"

def generate_case_id():
    now_str = datetime.now().strftime("%Y%m%d")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM cm_cases WHERE case_id LIKE ?", (f"CM-{now_str}-%",))
    count = c.fetchone() + 1
    conn.close()
    return f"CM-{now_str}-{count:03d}"

# ==========================================
# 3. ส่วนแสดงผล UI (Streamlit Layout)
# ==========================================
st.set_page_config(page_title="ระบบ Helpdesk & CM Tracking - USO SHF", page_icon="🛠️", layout="wide")

st.title("🛠️ ระบบบริหารจัดการและติดตามงานซ่อมแซมแก้ไข (CM Management)")
st.caption("โครงการเพิ่มประสิทธิภาพระบบโครงข่ายสื่อสารด้วยอุปกรณ์ทวนสัญญาณผ่านคลื่นความถี่สูง (SHF) - สำนักงาน กสทช.")

st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs([
    "📝 1. บันทึกรับแจ้งเหตุซ่อมใหม่", 
    "📊 2. ติดตามสถานะ & SLA", 
    "📦 3. ติดตามอุปกรณ์สำรอง (60 วัน)", 
    "📈 4. สรุปภาพรวม & ออกรายงาน"
])

# ------------------------------------------
# TAB 1: รับแจ้งเหตุซ่อมใหม่ (Helpdesk Intake)
# ------------------------------------------
with tab1:
    st.subheader("รับแจ้งข้อขัดข้องและออกเลข Case ID")
    
    with st.form("intake_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            station_name = st.text_input("ชื่อสถานี/จุดติดตั้ง *", placeholder="เช่น สถานีบ้านห้วยผา")
            province = st.selectbox("จังหวัด *", ["กาญจนบุรี", "ตาก", "แม่ฮ่องสอน", "เชียงใหม่", "อื่น ๆ"])
            reporter_name = st.text_input("ชื่อผู้แจ้งเหตุ *")
            reporter_phone = st.text_input("เบอร์โทรศัพท์ผู้แจ้ง (02 / มือถือ) *")
        
        with col2:
            equipment_type = st.selectbox("อุปกรณ์ที่เกิดข้อขัดข้อง *", [
                "ชุดอุปกรณ์ทวนสัญญาณผ่านคลื่นความถี่สูง (SHF)",
                "ระบบศูนย์ควบคุมสถานีแม่ข่าย (BSSC)",
                "ชุดสั่งการ (Dispatcher Console)",
                "ระบบบริหารจัดการ SD-WAN Controller",
                "ชุดอุปกรณ์ Gateway เชื่อมต่อ Analog",
                "สถานีแม่ข่ายแบบ 1 Carrier (Outdoor)",
                "อุปกรณ์กระจายสัญญาณ L3 Switch (24 Ports)",
                "เครื่องสำรองไฟฟ้า ขนาด 3 kVA",
                "เครื่องวิทยุลูกข่ายชนิดมือถือ",
                "เครื่องวิทยุลูกข่ายชนิดประจำที่ ณ ที่ทำการหมู่บ้าน"
            ])
            report_datetime = st.datetime_input("วัน-เวลาที่รับแจ้งเหตุ (Start SLA) *", datetime.now())
            issue_desc = st.text_area("รายละเอียดอาการเสีย/ข้อขัดข้อง *")
        
        submitted = st.form_submit_button("บันทึกการรับแจ้งเหตุ (Create Case)")
        
        if submitted:
            if not station_name or not reporter_name or not issue_desc:
                st.error("⚠️ กรุณากรอกข้อมูลที่มีเครื่องหมาย * ให้ครบถ้วน")
            else:
                case_id = generate_case_id()
                hours, sla_label = get_sla_info(equipment_type)
                sla_deadline = report_datetime + timedelta(hours=hours)
                
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute('''
                    INSERT INTO cm_cases (case_id, station_name, province, reporter_name, reporter_phone, 
                                        issue_desc, equipment_type, sla_category, report_time, sla_deadline, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (case_id, station_name, province, reporter_name, reporter_phone, 
                      issue_desc, equipment_type, sla_label, 
                      report_datetime.strftime("%Y-%m-%d %H:%M:%S"), 
                      sla_deadline.strftime("%Y-%m-%d %H:%M:%S"), "กำลังดำเนินการ"))
                conn.commit()
                conn.close()
                
                st.success(f"✅ บันทึกรับแจ้งเหตุเรียบร้อยแล้ว!")
                st.info(f"📌 **Case ID:** `{case_id}` | **ประเภท SLA:** {sla_label} | **ต้องแก้ไขเสร็จภายใน:** `{sla_deadline.strftime('%d/%m/%Y %H:%M')}`")

# ------------------------------------------
# TAB 2: ติดตามสถานะ & SLA (Tracking)
# ------------------------------------------
with tab2:
    st.subheader("ตารางติดตามสถานะงานซ่อม และการอัปเดตผลงาน")
    
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM cm_cases ORDER BY report_time DESC", conn)
    conn.close()
    
    if df.empty:
        st.info("ยังไม่มีข้อมูลการแจ้งซ่อมในระบบ")
    else:
        st.dataframe(df[[
            "case_id", "station_name", "equipment_type", "sla_category", 
            "report_time", "sla_deadline", "status"
        ]], use_container_width=True)
        
        st.markdown("---")
        st.subheader("🔄 อัปเดตผลการซ่อมแซมหน้างาน (Update Case Progress)")
        
        selected_case = st.selectbox("เลือก Case ID ที่ต้องการอัปเดต:", df["case_id"].tolist())
        case_info = df[df["case_id"] == selected_case].iloc
        
        st.write(f"**สถานี:** {case_info['station_name']} | **อุปกรณ์:** {case_info['equipment_type']} | **กำหนดเสร็จ:** {case_info['sla_deadline']}")
        
        with st.form("update_case_form"):
            col_a, col_b = st.columns(2)
            with col_a:
                status = st.selectbox("สถานะการซ่อม", ["กำลังดำเนินการ", "แก้ไขเรียบร้อยแล้ว", "รออะไหล่/นำอุปกรณ์สำรองมาเปลี่ยน"], index=0 if case_info['status']=="กำลังดำเนินการ" else 1)
                technician_name = st.text_input("ชื่อวิศวกรผู้เข้าซ่อม", value=case_info['technician_name'] if case_info['technician_name'] else "")
                original_sn = st.text_input("Serial Number อุปกรณ์เดิม", value=case_info['original_sn'] if case_info['original_sn'] else "")
                new_sn = st.text_input("Serial Number อุปกรณ์ใหม่ (ถ้ามี)", value=case_info['new_sn'] if case_info['new_sn'] else "")
            
            with col_b:
                is_spare = st.checkbox("มีการใช้อุปกรณ์สำรองชั่วคราวหรือไม่?", value=bool(case_info['is_spare_used']))
                spare_sn = st.text_input("S/N อุปกรณ์สำรองชั่วคราว", value=case_info['spare_sn'] if case_info['spare_sn'] else "")
                solution_desc = st.text_area("วิธีแก้ไข / สาเหตุของปัญหา", value=case_info['solution_desc'] if case_info['solution_desc'] else "")
                
            btn_update = st.form_submit_button("บันทึกการอัปเดต")
            
            if btn_update:
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                spare_install_date = datetime.now().strftime("%Y-%m-%d") if is_spare else None
                spare_return_deadline = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d") if is_spare else None
                completion_time = now_str if status == "แก้ไขเรียบร้อยแล้ว" else None
                
                c.execute('''
                    UPDATE cm_cases 
                    SET status=?, technician_name=?, solution_desc=?, original_sn=?, new_sn=?, 
                        is_spare_used=?, spare_sn=?, spare_install_date=?, spare_return_deadline=?, completion_time=?
                    WHERE case_id=?
                ''', (status, technician_name, solution_desc, original_sn, new_sn, 
                      1 if is_spare else 0, spare_sn, spare_install_date, spare_return_deadline, completion_time, selected_case))
                
                conn.commit()
                conn.close()
                st.success(f"อัปเดตข้อมูล Case ID: {selected_case} เรียบร้อยแล้ว!")
                st.rerun()

# ------------------------------------------
# TAB 3: ติดตามอุปกรณ์สำรอง 60 วัน (Spare Unit Tracking)
# ------------------------------------------
with tab3:
    st.subheader("รายการอุปกรณ์สำรองชั่วคราว (ต้องนำอุปกรณ์จริงส่งคืนภายใน 60 วัน)")
    
    conn = sqlite3.connect(DB_FILE)
    spare_df = pd.read_sql_query("SELECT case_id, station_name, equipment_type, spare_sn, spare_install_date, spare_return_deadline FROM cm_cases WHERE is_spare_used = 1", conn)
    conn.close()
    
    if spare_df.empty:
        st.info("ไม่มีรายการที่ใช้อุปกรณ์สำรองชั่วคราว")
    else:
        st.dataframe(spare_df, use_container_width=True)

# ------------------------------------------
# TAB 4: สรุปภาพรวม & ส่งออกรายงาน (Analytics & Report)
# ------------------------------------------
with tab4:
    st.subheader("สรุปสถิติผลการดำเนินงาน CM")
    
    conn = sqlite3.connect(DB_FILE)
    df_all = pd.read_sql_query("SELECT * FROM cm_cases", conn)
    conn.close()
    
    if not df_all.empty:
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("เคสทั้งหมด", len(df_all))
        col_m2.metric("กำลังดำเนินการ", len(df_all[df_all["status"] == "กำลังดำเนินการ"]))
        col_m3.metric("แก้ไขเรียบร้อยแล้ว", len(df_all[df_all["status"] == "แก้ไขเรียบร้อยแล้ว"]))
        
        st.markdown("---")
        st.subheader("ส่งออกข้อมูลเป็น CSV เพื่อส่ง กสทช.")
        csv = df_all.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 ดาวน์โหลดรายงาน CM ทั้งหมด (.csv)",
            data=csv,
            file_name=f"CM_Report_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
