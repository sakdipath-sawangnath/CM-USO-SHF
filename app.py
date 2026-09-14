import sqlite3
from datetime import datetime, timedelta
2
import pandas as pd
import streamlit as st

# ==========================================
# 1. การตั้งค่าระบบและฐานข้อมูล (Database Setup)
# ==========================================
DB_FILE = "cm_management.db"


def init_db():
  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  # ตารางเก็บบันทึกเคสการซ่อม (CM Cases)
  c.execute("""
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
    """)
  # ตารางเก็บรายชื่อสถานีที่นำเข้าจาก Excel
  c.execute("""
        CREATE TABLE IF NOT EXISTS stations (
            station_id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_name TEXT UNIQUE,
            province TEXT,
            district TEXT
        )
    """)
  conn.commit()
  conn.close()


init_db()


# ==========================================
# 2. ฟังก์ชันคำนวณ SLA และ Helper Functions
# ==========================================
def get_sla_info(equipment):
  sla_3h = [
      "ระบบศูนย์ควบคุมสถานีแม่ข่าย (BSSC)",
      "ชุดสั่งการ (Dispatcher Console)",
      "ระบบบริหารจัดการ SD-WAN Controller",
  ]
  sla_3d = [
      "ชุดอุปกรณ์ทวนสัญญาณผ่านคลื่นความถี่สูง (SHF)",
      "ชุดอุปกรณ์ Gateway เชื่อมต่อ Analog",
      "สถานีแม่ข่ายแบบ 1 Carrier (Outdoor)",
      "อุปกรณ์กระจายสัญญาณ L3 Switch (24 Ports)",
      "เครื่องสำรองไฟฟ้า ขนาด 3 kVA",
  ]
  sla_4d = [
      "เครื่องวิทยุลูกข่ายชนิดมือถือ",
      "เครื่องวิทยุลูกข่ายชนิดประจำที่ ณ ที่ทำการหมู่บ้าน",
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
  c.execute(
      "SELECT COUNT(*) FROM cm_cases WHERE case_id LIKE ?", (f"CM-{now_str}-%",)
  )
  row = c.fetchone()
  count = (row if row and row is not None else 0) + 1
  conn.close()
  return f"CM-{now_str}-{count:03d}"


def get_station_list():
  conn = sqlite3.connect(DB_FILE)
  df = pd.read_sql_query(
      "SELECT station_name, province FROM stations ORDER BY station_name", conn
  )
  conn.close()
  return df


# ==========================================
# 3. ส่วนแสดงผล UI (Streamlit Layout)
# ==========================================
st.set_page_config(
    page_title="ระบบ Helpdesk & CM Tracking - USO SHF",
    page_icon="🛠️",
    layout="wide",
)

st.title("🛠️ ระบบบริหารจัดการและติดตามงานซ่อมแซมแก้ไข (CM Management)")
st.caption(
    "โครงการเพิ่มประสิทธิภาพระบบโครงข่ายสื่อสารด้วยอุปกรณ์ทวนสัญญาณผ่านคลื่นความถี่สูง"
    " (SHF) - สำนักงาน กสทช."
)

st.markdown("---")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📝 1. บันทึกรับแจ้งเหตุซ่อมใหม่",
    "📊 2. ติดตามสถานะ & อัปเดตงานซ่อม",
    "📦 3. ติดตามอุปกรณ์สำรอง (60 วัน)",
    "📁 4. นำเข้าข้อมูลสถานี (Excel)",
    "📈 5. Executive Dashboard",
])

# ------------------------------------------
# TAB 1: รับแจ้งเหตุซ่อมใหม่ (Helpdesk Intake)
# ------------------------------------------
with tab1:
  st.subheader("รับแจ้งข้อขัดข้องและออกเลข Case ID")

  stations_df = get_station_list()
  station_options = (
      ["[+] กรอกชื่อสถานีเอง (นอกระบบ)"] + stations_df["station_name"].tolist()
      if not stations_df.empty
      else ["[+] กรอกชื่อสถานีเอง (นอกระบบ)"]
  )

  with st.form("intake_form", clear_on_submit=True):
    col1, col2 = st.columns(2)

    with col1:
      selected_station_opt = st.selectbox(
          "เลือกสถานี/จุดติดตั้ง *", station_options
      )

      if selected_station_opt == "[+] กรอกชื่อสถานีเอง (นอกระบบ)":
        station_name = st.text_input(
            "ระบุชื่อสถานี *", placeholder="เช่น สถานีบ้านห้วยผา"
        )
        province = st.selectbox(
            "จังหวัด *",
            ["กาญจนบุรี", "ตาก", "แม่ฮ่องสอน", "เชียงใหม่", "อื่น ๆ"],
        )
      else:
        station_name = selected_station_opt
        auto_province = (
            stations_df[stations_df["station_name"] == station_name][
                "province"
            ].values
            if not stations_df.empty
            else "กาญจนบุรี"
        )
        province = st.text_input("จังหวัด", value=auto_province, disabled=True)

      reporter_name = st.text_input("ชื่อผู้แจ้งเหตุ *")
      reporter_phone = st.text_input("เบอร์โทรศัพท์ผู้แจ้ง (02 / มือถือ) *")

    with col2:
      equipment_type = st.selectbox(
          "อุปกรณ์ที่เกิดข้อขัดข้อง *",
          [
              "ชุดอุปกรณ์ทวนสัญญาณผ่านคลื่นความถี่สูง (SHF)",
              "ระบบศูนย์ควบคุมสถานีแม่ข่าย (BSSC)",
              "ชุดสั่งการ (Dispatcher Console)",
              "ระบบบริหารจัดการ SD-WAN Controller",
              "ชุดอุปกรณ์ Gateway เชื่อมต่อ Analog",
              "สถานีแม่ข่ายแบบ 1 Carrier (Outdoor)",
              "อุปกรณ์กระจายสัญญาณ L3 Switch (24 Ports)",
              "เครื่องสำรองไฟฟ้า ขนาด 3 kVA",
              "เครื่องวิทยุลูกข่ายชนิดมือถือ",
              "เครื่องวิทยุลูกข่ายชนิดประจำที่ ณ ที่ทำการหมู่บ้าน",
          ],
      )
      report_datetime = st.datetime_input(
          "วัน-เวลาที่รับแจ้งเหตุ (Start SLA) *", datetime.now()
      )
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
        c.execute(
            """
                    INSERT INTO cm_cases (case_id, station_name, province, reporter_name, reporter_phone, 
                                        issue_desc, equipment_type, sla_category, report_time, sla_deadline, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
            (
                case_id,
                station_name,
                province,
                reporter_name,
                reporter_phone,
                issue_desc,
                equipment_type,
                sla_label,
                report_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                sla_deadline.strftime("%Y-%m-%d %H:%M:%S"),
                "กำลังดำเนินการ",
            ),
        )
        conn.commit()
        conn.close()

        st.success("✅ บันทึกรับแจ้งเหตุเรียบร้อยแล้ว!")
        st.info(
            f"📌 **Case ID:** `{case_id}` | **ประเภท SLA:** {sla_label} |"
            f" **กำหนดเสร็จภายใน:**"
            f" `{sla_deadline.strftime('%d/%m/%Y %H:%M')}`"
        )

# ------------------------------------------
# TAB 2: ติดตามสถานะ & อัปเดตงานซ่อม
# ------------------------------------------
with tab2:
  st.subheader("ตารางติดตามสถานะงานซ่อม และการอัปเดตผลงาน")

  conn = sqlite3.connect(DB_FILE)
  df = pd.read_sql_query(
      "SELECT * FROM cm_cases ORDER BY report_time DESC", conn
  )
  conn.close()

  if df.empty:
    st.info("ยังไม่มีข้อมูลการแจ้งซ่อมในระบบ")
  else:
    st.dataframe(
        df[[
            "case_id",
            "station_name",
            "province",
            "equipment_type",
            "sla_category",
            "report_time",
            "sla_deadline",
            "status",
        ]],
        use_container_width=True,
    )

    st.markdown("---")
    st.subheader("🔄 อัปเดตผลการซ่อมแซมหน้างาน & ปิดงานซ่อม")

    selected_case = st.selectbox(
        "เลือก Case ID ที่ต้องการอัปเดต/ปิดงาน:", df["case_id"].tolist()
    )
    case_info = df[df["case_id"] == selected_case].iloc

    st.write(
        f"**สถานี:** {case_info['station_name']} | **อุปกรณ์:**"
        f" {case_info['equipment_type']} | **กำหนดเสร็จ:**"
        f" {case_info['sla_deadline']}"
    )

    with st.form("update_case_form"):
      col_a, col_b = st.columns(2)
      with col_a:
        status = st.selectbox(
            "สถานะการซ่อม",
            [
                "กำลังดำเนินการ",
                "แก้ไขเรียบร้อยแล้ว",
                "รออะไหล่/นำอุปกรณ์สำรองมาเปลี่ยน",
            ],
            index=0 if case_info["status"] == "กำลังดำเนินการ" else 1,
        )
        technician_name = st.text_input(
            "ชื่อวิศวกรผู้เข้าซ่อม",
            value=(
                case_info["technician_name"]
                if case_info["technician_name"]
                else ""
            ),
        )
        original_sn = st.text_input(
            "Serial Number อุปกรณ์เดิม",
            value=case_info["original_sn"] if case_info["original_sn"] else "",
        )
        new_sn = st.text_input(
            "Serial Number อุปกรณ์ใหม่ (ถ้ามี)",
            value=case_info["new_sn"] if case_info["new_sn"] else "",
        )

      with col_b:
        is_spare = st.checkbox(
            "มีการใช้อุปกรณ์สำรองชั่วคราวหรือไม่?",
            value=bool(case_info["is_spare_used"]),
        )
        spare_sn = st.text_input(
            "S/N อุปกรณ์สำรองชั่วคราว",
            value=case_info["spare_sn"] if case_info["spare_sn"] else "",
        )
        solution_desc = st.text_area(
            "วิธีแก้ไข / สาเหตุของปัญหา",
            value=(
                case_info["solution_desc"]
                if case_info["solution_desc"]
                else ""
            ),
        )

      st.markdown("<br>", unsafe_allow_html=True)
      btn_col1, btn_col2 = st.columns(2)
      with btn_col1:
        btn_update = st.form_submit_button("💾 บันทึกอัปเดตสถานะ")
      with btn_col2:
        btn_close_case = st.form_submit_button("✅ ปิดงานซ่อม (Close Case)")

      if btn_update or btn_close_case:
        final_status = "แก้ไขเรียบร้อยแล้ว" if btn_close_case else status
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        spare_install_date = (
            datetime.now().strftime("%Y-%m-%d") if is_spare else None
        )
        spare_return_deadline = (
            (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")
            if is_spare
            else None
        )
        completion_time = (
            now_str if final_status == "แก้ไขเรียบร้อยแล้ว" else None
        )

        c.execute(
            """
                    UPDATE cm_cases 
                    SET status=?, technician_name=?, solution_desc=?, original_sn=?, new_sn=?, 
                        is_spare_used=?, spare_sn=?, spare_install_date=?, spare_return_deadline=?, completion_time=?
                    WHERE case_id=?
                """,
            (
                final_status,
                technician_name,
                solution_desc,
                original_sn,
                new_sn,
                1 if is_spare else 0,
                spare_sn,
                spare_install_date,
                spare_return_deadline,
                completion_time,
                selected_case,
            ),
        )

        conn.commit()
        conn.close()

        if btn_close_case:
          st.success(f"🎉 ปิดงานซ่อม Case ID: {selected_case} เรียบร้อยแล้ว!")
        else:
          st.success(f"💾 บันทึกอัปเดตข้อมูล Case ID: {selected_case} เรียบร้อยแล้ว!")
        st.rerun()

# ------------------------------------------
# TAB 3: ติดตามอุปกรณ์สำรอง 60 วัน
# ------------------------------------------
with tab3:
  st.subheader(
      "รายการอุปกรณ์สำรองชั่วคราว (ต้องนำอุปกรณ์จริงส่งคืนภายใน 60 วัน)"
  )

  conn = sqlite3.connect(DB_FILE)
  spare_df = pd.read_sql_query(
      "SELECT case_id, station_name, equipment_type, spare_sn,"
      " spare_install_date, spare_return_deadline FROM cm_cases WHERE"
      " is_spare_used = 1",
      conn,
  )
  conn.close()

  if spare_df.empty:
    st.info("ไม่มีรายการที่ใช้อุปกรณ์สำรองชั่วคราว")
  else:
    st.dataframe(spare_df, use_container_width=True)

# ------------------------------------------
# TAB 4: นำเข้าข้อมูลสถานีจาก Excel
# ------------------------------------------
with tab4:
  st.subheader("📥 อัปโหลดไฟล์ Excel / CSV รายชื่อสถานี")
  st.caption(
      "อัปโหลดไฟล์เพื่อใช้เป็นตัวเลือก Dropdown"
      " อัตโนมัติในการบันทึกแจ้งเหตุซ่อม"
  )

  uploaded_file = st.file_uploader(
      "เลือกไฟล์ Excel (.xlsx, .xls) หรือ CSV", type=["xlsx", "xls", "csv"]
  )

  if uploaded_file is not None:
    try:
      if uploaded_file.name.endswith(".csv"):
        excel_df = pd.read_csv(uploaded_file)
      else:
        excel_df = pd.read_excel(uploaded_file)

      st.write("🔍 **ตัวอย่างข้อมูลในไฟล์:**")
      st.dataframe(excel_df.head(5), use_container_width=True)

      st.markdown("---")
      st.write("⚙️ **จับคู่คอลัมน์ข้อมูล:**")

      col_u1, col_u2 = st.columns(2)
      with col_u1:
        station_col = st.selectbox("คอลัมน์ชื่อสถานี", excel_df.columns)
      with col_u2:
        province_col = st.selectbox("คอลัมน์จังหวัด", excel_df.columns)

      if st.button("💾 บันทึกรายชื่อสถานีเข้าฐานข้อมูล"):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        success_count = 0
        for _, row in excel_df.iterrows():
          s_name = str(row[station_col]).strip()
          p_name = str(row[province_col]).strip()

          if s_name and s_name != "nan":
            try:
              c.execute(
                  "INSERT OR REPLACE INTO stations (station_name, province)"
                  " VALUES (?, ?)",
                  (s_name, p_name),
              )
              success_count += 1
            except Exception:
              pass

        conn.commit()
        conn.close()
        st.success(
            f"✅ บันทึกรายชื่อสถานีเรียบร้อยแล้วจำนวน {success_count} รายการ!"
        )
        st.rerun()

    except Exception as err:
      st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์: {err}")

  st.markdown("---")
  st.subheader("📋 รายชื่อสถานีในระบบปัจจุบัน")
  current_stations = get_station_list()
  if not current_stations.empty:
    st.dataframe(current_stations, use_container_width=True)
  else:
    st.info(
        "ยังไม่มีข้อมูลสถานีในระบบ สามารถนำเข้าผ่านไฟล์ Excel ด้านบนได้ครับ"
    )

# ------------------------------------------
# TAB 5: Executive Dashboard & Analytics
# ------------------------------------------
with tab5:
  st.subheader("📈 สรุปภาพรวมและสถิติผลการดำเนินงาน CM")

  conn = sqlite3.connect(DB_FILE)
  df_dash = pd.read_sql_query("SELECT * FROM cm_cases", conn)
  conn.close()

  if df_dash.empty:
    st.info("ยังไม่มีข้อมูลสำหรับแสดงผลในแดชบอร์ด")
  else:
    # การ์ดสรุป KPI
    total_cases = len(df_dash)
    pending_cases = len(df_dash[df_dash["status"] == "กำลังดำเนินการ"])
    completed_cases = len(df_dash[df_dash["status"] == "แก้ไขเรียบร้อยแล้ว"])
    spare_cases = len(df_dash[df_dash["is_spare_used"] == 1])

    # คำนวณ % การแก้ไขสำเร็จ
    success_rate = (
        (completed_cases / total_cases * 100) if total_cases > 0 else 0
    )

    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric("เคสทั้งหมด", f"{total_cases} เคส")
    kpi2.metric(
        "กำลังดำเนินการ",
        f"{pending_cases} เคส",
        delta=f"-{pending_cases}" if pending_cases > 0 else "0",
        delta_color="inverse",
    )
    kpi3.metric(
        "แก้ไขเรียบร้อย", f"{completed_cases} เคส", delta=f"{success_rate:.1f}%"
    )
    kpi4.metric("ใช้อุปกรณ์สำรอง", f"{spare_cases} รายการ")
    kpi5.metric("อัตราซ่อมสำเร็จ", f"{success_rate:.1f}%")

    st.markdown("---")

    # กราฟวิเคราะห์ข้อมูล
    g_col1, g_col2 = st.columns(2)

    with g_col1:
      st.write("📊 **สัดส่วนสถานะงานซ่อม**")
      status_counts = df_dash["status"].value_counts()
      st.bar_chart(status_counts)

    with g_col2:
      st.write("📍 **จำนวนเคสแยกตามจังหวัด**")
      province_counts = df_dash["province"].value_counts()
      st.bar_chart(province_counts)

    st.markdown("---")
    st.write("🛠️ **จำนวนเคสแยกตามประเภทอุปกรณ์**")
    equip_counts = df_dash["equipment_type"].value_counts()
    st.bar_chart(equip_counts)

    st.markdown("---")
    st.subheader("📥 ดาวน์โหลดข้อมูลสรุปเพื่อจัดทำรายงานส่ง กสทช.")
    csv_data = df_dash.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="📥 ดาวน์โหลดรายงาน CM ทั้งหมด (.csv)",
        data=csv_data,
        file_name=f"CM_Report_Summary_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )
