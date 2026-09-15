import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ==========================================
# 1. การตั้งค่าระบบและธีมหน้าเว็บ (Page Setup)
# ==========================================
st.set_page_config(
    page_title="Executive Dashboard - Corrective Maintenance (CM)",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS เพื่อตกแต่ง UI ให้เป็น Modern Executive Dashboard
st.markdown(
    """
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric {
        background-color: #ffffff;
        padding: 18px;
        border-radius: 12px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        border: 1px solid #e9ecef;
    }
    .status-badge-green { background-color: #d4edda; color: #155724; padding: 4px 10px; border-radius: 12px; font-weight: bold; }
    .status-badge-yellow { background-color: #fff3cd; color: #856404; padding: 4px 10px; border-radius: 12px; font-weight: bold; }
    .status-badge-red { background-color: #f8d7da; color: #721c24; padding: 4px 10px; border-radius: 12px; font-weight: bold; }
    </style>
""",
    unsafe_allow_html=True,
)

DB_FILE = "cm_management.db"


# ==========================================
# 2. การจัดการฐานข้อมูล (Database Initialization)
# ==========================================
def init_db():
  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  # ตารางเก็บบันทึกเคสการซ่อม
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
  # ตารางเก็บรายชื่อสถานี
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
# 3. ฟังก์ชันคำนวณ SLA และ Helper Functions
# ==========================================
def get_sla_info(equipment):
  """คำนวณระยะเวลา SLA ตามประเภทอุปกรณ์"""
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
  """ออกรหัส Case ID อัตโนมัติ รูปแบบ CM-SHF-YYYY-XXXX"""
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


def load_data():
  """โหลดข้อมูลเคสทั้งหมดจากฐานข้อมูล SQLite"""
  conn = sqlite3.connect(DB_FILE)
  df = pd.read_sql_query("SELECT * FROM cm_cases", conn)
  conn.close()
  return df


def get_station_list():
  """ดึงรายชื่อสถานีทั้งหมด"""
  conn = sqlite3.connect(DB_FILE)
  df = pd.read_sql_query(
      "SELECT station_name, province FROM stations ORDER BY station_name", conn
  )
  conn.close()
  return df


# โหลดข้อมูลหลัก
df_raw = load_data()

# ==========================================
# 4. ส่วนตัวกรองข้อมูล (Sidebar Filter Panel)
# ==========================================
st.sidebar.title("🔍 ตัวกรองข้อมูล (Filters)")
st.sidebar.markdown("---")

if not df_raw.empty:
  # แปลงคอลัมน์วันที่
  df_raw["report_time_dt"] = pd.to_datetime(df_raw["report_time"])
  df_raw["sla_deadline_dt"] = pd.to_datetime(df_raw["sla_deadline"])
  df_raw["completion_time_dt"] = pd.to_datetime(df_raw["completion_time"])

  # Filter 1: ช่วงวันที่รับแจ้งเหตุ
  min_date = df_raw["report_time_dt"].min().date()
  max_date = df_raw["report_time_dt"].max().date()
  date_range = st.sidebar.date_input(
      "📅 ช่วงวันที่รับแจ้งเหตุ",
      value=(min_date, max_date),
      min_value=min_date,
      max_value=max_date,
  )

  # Filter 2: จังหวัด
  province_list = ["ทั้งหมด"] + sorted(
      df_raw["province"].dropna().unique().tolist()
  )
  selected_province = st.sidebar.selectbox("📍 จังหวัด / พื้นที่บริการ", province_list)

  # Filter 3: ประเภทอุปกรณ์
  equip_list = ["ทั้งหมด"] + sorted(
      df_raw["equipment_type"].dropna().unique().tolist()
  )
  selected_equip = st.sidebar.selectbox("🛠️ ประเภทอุปกรณ์", equip_list)

  # Filter 4: สถานะงานซ่อม
  status_list = ["ทั้งหมด"] + sorted(
      df_raw["status"].dropna().unique().tolist()
  )
  selected_status = st.sidebar.selectbox("🔄 สถานะงานซ่อม", status_list)

  # ประมวลผลการกรองข้อมูล
  df_filtered = df_raw.copy()

  if isinstance(date_range, tuple) and len(date_range) == 2:
    start_d, end_d = date_range
    df_filtered = df_filtered[
        (df_filtered["report_time_dt"].dt.date >= start_d)
        & (df_filtered["report_time_dt"].dt.date <= end_d)
    ]

  if selected_province != "ทั้งหมด":
    df_filtered = df_filtered[df_filtered["province"] == selected_province]

  if selected_equip != "ทั้งหมด":
    df_filtered = df_filtered[df_filtered["equipment_type"] == selected_equip]

  if selected_status != "ทั้งหมด":
    df_filtered = df_filtered[df_filtered["status"] == selected_status]

else:
  df_filtered = pd.DataFrame()

# ==========================================
# 5. ส่วนแสดงผล UI หลัก (Header & Tabs)
# ==========================================
st.title("🛠️ Corrective Maintenance (CM) Executive Dashboard")
st.caption(
    "ระบบบริหารจัดการและติดตามงานซ่อมแซมแก้ไขอุปกรณ์โครงข่ายสถานีบริการ"
    " (USO SHF) - สำนักงาน กสทช."
)

tab_dash, tab_intake, tab_update, tab_spare, tab_import = st.tabs([
    "📈 Executive Dashboard",
    "📝 บันทึกรับแจ้งเหตุใหม่",
    "🔄 อัปเดต & ปิดงานซ่อม",
    "📦 ติดตามอุปกรณ์สำรอง (60 วัน)",
    "📁 นำเข้าข้อมูลสถานี (Excel)",
])

# ------------------------------------------
# TAB 1: EXECUTIVE DASHBOARD & VISUALIZATIONS
# ------------------------------------------
with tab_dash:
  if df_filtered.empty:
    st.warning(
        "⚠️ ยังไม่มีข้อมูลเคสแจ้งซ่อมในระบบ หรือไม่พบข้อมูลตามเงื่อนไขตัวกรอง"
    )
  else:
    now = datetime.now()

    # ฟังก์ชันประมวลผล SLA Status
    def calc_sla_status(row):
      if row["status"] == "แก้ไขเรียบร้อยแล้ว":
        if (
            pd.notna(row["completion_time_dt"])
            and row["completion_time_dt"] <= row["sla_deadline_dt"]
        ):
          return "ทันเวลา (On-Time)"
        else:
          return "เกินกำหนด (Overdue)"
      else:
        if now <= row["sla_deadline_dt"]:
          return "อยู่ใน SLA (In-SLA)"
        else:
          return "เกินกำหนด (Overdue)"

    df_filtered["sla_status"] = df_filtered.apply(calc_sla_status, axis=1)

    # --------------------------------------
    # 2. KPI SUMMARY CARDS (6 CARDS)
    # --------------------------------------
    total_cases = len(df_filtered)
    pending_cases = len(
        df_filtered[
            df_filtered["status"].isin(
                ["กำลังดำเนินการ", "รออะไหล่/นำอุปกรณ์สำรองมาเปลี่ยน"]
            )
        ]
    )
    resolved_cases = len(
        df_filtered[df_filtered["status"] == "แก้ไขเรียบร้อยแล้ว"]
    )
    active_spares = len(df_filtered[df_filtered["is_spare_used"] == 1])

    # อัตราซ่อมทัน SLA (%)
    completed_df = df_filtered[
        df_filtered["status"] == "แก้ไขเรียบร้อยแล้ว"
    ].copy()
    on_time_count = len(
        completed_df[completed_df["sla_status"] == "ทันเวลา (On-Time)"]
    )
    sla_compliance_rate = (
        (on_time_count / len(completed_df) * 100)
        if len(completed_df) > 0
        else 0.0
    )

    # คำนวณ MTTR (Mean Time to Repair - ชั่วโมง)
    if not completed_df.empty and completed_df["completion_time_dt"].notna().any():
      repair_times_hrs = (
          completed_df["completion_time_dt"] - completed_df["report_time_dt"]
      ).dt.total_seconds() / 3600.0
      mttr_val = repair_times_hrs.mean()
      mttr_display = (
          f"{mttr_val:.1f} ชม."
          if mttr_val < 48
          else f"{mttr_val/24.0:.1f} วัน"
      )
    else:
      mttr_display = "N/A"

    kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)
    kpi1.metric("📋 เคสทั้งหมด", f"{total_cases:,} เคส")
    kpi2.metric(
        "⏳ กำลังดำเนินการ",
        f"{pending_cases:,} เคส",
        delta=f"-{pending_cases}" if pending_cases > 0 else "0",
        delta_color="inverse",
    )
    kpi3.metric("✅ ซ่อมเสร็จแล้ว", f"{resolved_cases:,} เคส")
    kpi4.metric("🎯 SLA Compliance", f"{sla_compliance_rate:.1f}%")
    kpi5.metric("⏱️ MTTR (เฉลี่ยซ่อม)", mttr_display)
    kpi6.metric("📦 อุปกรณ์สำรอง", f"{active_spares:,} รายการ")

    st.markdown("---")

    # --------------------------------------
    # 3. INTERACTIVE VISUALIZATIONS (PLOTLY)
    # --------------------------------------
    row1_col1, row1_col2 = st.columns(2)

    with row1_col1:
      # Chart 1: Status Breakdown (Donut Chart)
      status_counts = (
          df_filtered["status"].value_counts().reset_index()
      )
      status_counts.columns = ["Status", "Count"]
      fig_status = px.pie(
          status_counts,
          values="Count",
          names="Status",
          title="📊 สัดส่วนสถานะงานซ่อม (Status Breakdown)",
          hole=0.45,
          color_discrete_sequence=px.colors.qualitative.Pastel,
      )
      fig_status.update_traces(textposition="inside", textinfo="percent+label")
      st.plotly_chart(fig_status, use_container_width=True)

    with row1_col2:
      # Chart 2: SLA Performance (On-Time vs Overdue)
      sla_counts = df_filtered["sla_status"].value_counts().reset_index()
      sla_counts.columns = ["SLA_Status", "Count"]
      color_map = {
          "ทันเวลา (On-Time)": "#2ecc71",
          "อยู่ใน SLA (In-SLA)": "#f1c40f",
          "เกินกำหนด (Overdue)": "#e74c3c",
      }
      fig_sla = px.pie(
          sla_counts,
          values="Count",
          names="SLA_Status",
          title="🎯 ประสิทธิภาพการซ่อมตาม SLA (SLA Performance)",
          hole=0.45,
          color="SLA_Status",
          color_discrete_map=color_map,
      )
      fig_sla.update_traces(textposition="inside", textinfo="percent+label")
      st.plotly_chart(fig_sla, use_container_width=True)

    row2_col1, row2_col2 = st.columns(2)

    with row2_col1:
      # Chart 3: Cases by Equipment Type (Horizontal Bar Chart)
      equip_counts = (
          df_filtered["equipment_type"].value_counts().reset_index()
      )
      equip_counts.columns = ["Equipment", "Count"]
      equip_counts = equip_counts.sort_values(by="Count", ascending=True)
      fig_equip = px.bar(
          equip_counts,
          x="Count",
          y="Equipment",
          orientation="h",
          title="🛠️ อันดับประเภทอุปกรณ์ที่เกิดข้อขัดข้องสูงสุด",
          text="Count",
          color="Count",
          color_continuous_scale="Blues",
      )
      fig_equip.update_layout(showlegend=False)
      st.plotly_chart(fig_equip, use_container_width=True)

    with row2_col2:
      # Chart 4: Regional / Province Distribution (Bar Chart)
      prov_counts = (
          df_filtered["province"].value_counts().reset_index()
      )
      prov_counts.columns = ["Province", "Count"]
      fig_prov = px.bar(
          prov_counts,
          x="Province",
          y="Count",
          title="📍 จำนวนเคสซ่อมแยกตามจังหวัด / พื้นที่บริการ",
          text="Count",
          color="Province",
          color_discrete_sequence=px.colors.qualitative.Set3,
      )
      fig_prov.update_layout(showlegend=False)
      st.plotly_chart(fig_prov, use_container_width=True)

    st.markdown("---")

    # --------------------------------------
    # 5. RECENT INCIDENT TABLE & EXPORT
    # --------------------------------------
    st.subheader("📋 ตารางติดตามรายการเคสซ่อม (Recent Incident Table)")

    col_search, col_export_csv, col_export_excel = st.columns()

    with col_search:
      search_term = st.text_input(
          "🔍 ค้นหา (Case ID, ชื่อสถานี, หรือผู้รับผิดชอบ)",
          placeholder="พิมพ์คำค้นหา...",
      )

    display_df = df_filtered.copy()

    if search_term:
      display_df = display_df[
          display_df["case_id"]
          .str.contains(search_term, case=False, na=False)
          | display_df["station_name"].str.contains(
              search_term, case=False, na=False
          )
          | display_df["technician_name"].str.contains(
              search_term, case=False, na=False
          )
      ]

    # ฟังก์ชันแสดง Badge สถานะ
    def format_sla_badge(val):
      if val == "ทันเวลา (On-Time)":
        return "🟢 ทันเวลา"
      elif val == "อยู่ใน SLA (In-SLA)":
        return "🟡 อยู่ใน SLA"
      else:
        return "🔴 เกินกำหนด (Overdue)"

    display_df["SLA_Status_Badge"] = display_df["sla_status"].apply(
        format_sla_badge
    )

    # จัดการคอลัมน์สำหรับแสดงผลในตาราง
    table_df = display_df[[
        "case_id",
        "station_name",
        "province",
        "equipment_type",
        "report_time",
        "sla_deadline",
        "status",
        "SLA_Status_Badge",
        "technician_name",
    ]].copy()

    table_df.columns = [
        "Case ID",
        "ชื่อสถานี",
        "จังหวัด",
        "อุปกรณ์",
        "วันที่รับแจ้ง",
        "กำหนด SLA",
        "สถานะงาน",
        "สถานะ SLA",
        "ผู้รับผิดชอบ",
    ]

    st.dataframe(table_df, use_container_width=True, hide_index=True)

    # ปุ่ม Export
    with col_export_csv:
      csv_data = display_df.to_csv(index=False).encode("utf-8-sig")
      st.download_button(
          label="📥 Export CSV",
          data=csv_data,
          file_name=f"CM_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
          mime="text/csv",
          use_container_width=True,
      )

    with col_export_excel:
      # สำหรับไฟล์ Excel
      import io

      output = io.BytesIO()
      with pd.ExcelWriter(output, engine="openpyxl") as writer:
        display_df.to_excel(writer, index=False, sheet_name="CM_Cases")
      excel_data = output.getvalue()

      st.download_button(
          label="📊 Export Excel",
          data=excel_data,
          file_name=f"CM_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
          mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          use_container_width=True,
      )

# ------------------------------------------
# TAB 2: บันทึกรับแจ้งเหตุใหม่ (Helpdesk Intake)
# ------------------------------------------
with tab_intake:
  st.subheader("📝 รับแจ้งข้อขัดข้องและออกเลข Case ID ใหม่")

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
        st.rerun()

# ------------------------------------------
# TAB 3: อัปเดต & ปิดงานซ่อม (Update Progress)
# ------------------------------------------
with tab_update:
  st.subheader("🔄 อัปเดตผลการซ่อมแซมหน้างาน & ปิดงานซ่อม")

  if df_raw.empty:
    st.info("ยังไม่มีข้อมูลเคสแจ้งซ่อมในระบบ")
  else:
    selected_case = st.selectbox(
        "เลือก Case ID ที่ต้องการอัปเดต:", df_raw["case_id"].tolist()
    )
    case_info = df_raw[df_raw["case_id"] == selected_case].iloc

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
# TAB 4: ติดตามอุปกรณ์สำรอง (Spare Parts)
# ------------------------------------------
with tab_spare:
  st.subheader(
      "📦 รายการอุปกรณ์สำรองชั่วคราว (กำหนดคืนอุปกรณ์จริงภายใน 60 วัน)"
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
    st.info("ไม่มีรายการที่ใช้อุปกรณ์สำรองชั่วคราวในขณะนี้")
  else:
    st.dataframe(spare_df, use_container_width=True, hide_index=True)

# ------------------------------------------
# TAB 5: นำเข้าข้อมูลสถานี (Excel Import)
# ------------------------------------------
with tab_import:
  st.subheader("📁 อัปโหลดไฟล์ Excel / CSV รายชื่อสถานี")

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
    st.dataframe(current_stations, use_container_width=True, hide_index=True)
