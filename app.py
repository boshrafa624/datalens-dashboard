import io
from datetime import date
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="DataLens | لوحة تحليل البيانات",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Theme ----------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Cairo', sans-serif; }
    .stApp { background: linear-gradient(135deg, #f5f8fc 0%, #eef3f9 100%); }
    .hero {
        padding: 1.5rem 1.8rem; border-radius: 22px; color: white;
        background: linear-gradient(120deg, #16324f 0%, #246a73 58%, #4b9aaa 100%);
        margin-bottom: 1.2rem; box-shadow: 0 10px 28px rgba(22,50,79,.14);
    }
    .hero h1 { margin: 0; font-size: 2.1rem; font-weight: 800; }
    .hero p { margin: .35rem 0 0; opacity: .9; font-size: 1rem; }
    div[data-testid="stMetric"] {
        background: white; padding: 1rem 1.1rem; border-radius: 16px;
        border: 1px solid #e3eaf2; box-shadow: 0 5px 18px rgba(28,54,83,.04);
    }
    div[data-testid="stMetricLabel"] { color: #60758b; }
    .section-title { color: #16324f; font-size: 1.25rem; font-weight: 800; margin: .5rem 0; }
    .small-note { color: #60758b; font-size: .9rem; }
    section[data-testid="stSidebar"] { background: #edf3f8; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero" dir="rtl">
  <h1>📊 DataLens — لوحة تحليل البيانات</h1>
  <p>استكشف بياناتك، صفِّها، وافهم المؤشرات الرئيسية من خلال لوحة تفاعلية بسيطة.</p>
</div>
""", unsafe_allow_html=True)

# ---------- Data generation ----------
@st.cache_data
def make_demo_data(n: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    departments = ["تقنية المعلومات", "المبيعات", "الموارد البشرية", "المالية", "العمليات", "التسويق"]
    cities = ["حلب", "إدلب", "دمشق", "حمص", "اللاذقية"]
    names = ["أحمد", "سارة", "محمد", "نور", "عمر", "ليان", "خالد", "ريم", "ياسمين", "علي",
             "مريم", "سامر", "جود", "رامي", "تالا", "كريم", "هبة", "أنس", "لانا", "فادي"]
    start = pd.Timestamp("2023-01-01")
    dates = start + pd.to_timedelta(rng.integers(0, 1000, n), unit="D")
    salary = rng.normal(850, 260, n).clip(350, 2200).round(0).astype(int)
    performance = rng.normal(3.6, .75, n).clip(1, 5).round(1)
    return pd.DataFrame({
        "رقم الموظف": np.arange(1001, 1001+n),
        "اسم الموظف": rng.choice(names, n),
        "القسم": rng.choice(departments, n, p=[.2, .22, .12, .12, .2, .14]),
        "المدينة": rng.choice(cities, n),
        "الراتب": salary,
        "تقييم الأداء": performance,
        "تاريخ التوظيف": pd.to_datetime(dates),
        "سنوات الخبرة": rng.integers(0, 16, n),
    })

# ---------- Sidebar controls ----------
with st.sidebar:
    st.markdown("## ⚙️ إعدادات البيانات")
    data_source = st.radio("مصدر البيانات", ["بيانات تجريبية", "رفع ملف CSV"], index=0)
    if data_source == "بيانات تجريبية":
        row_count = st.slider("عدد السجلات التجريبية", 50, 2000, 500, step=50)
        raw_df = make_demo_data(row_count)
        st.caption("البيانات المعروضة وهمية ومولّدة لأغراض التجربة.")
    else:
        uploaded = st.file_uploader("ارفع ملف CSV", type=["csv"])
        if uploaded is None:
            st.info("ارفع ملف CSV للبدء، أو اختر «بيانات تجريبية».")
            st.stop()
        try:
            raw_df = pd.read_csv(uploaded)
        except UnicodeDecodeError:
            uploaded.seek(0)
            raw_df = pd.read_csv(uploaded, encoding="utf-8-sig")
        except Exception as exc:
            st.error(f"تعذّر قراءة الملف: {exc}")
            st.stop()
        if raw_df.empty:
            st.warning("الملف لا يحتوي على بيانات.")
            st.stop()

    st.divider()
    st.markdown("### 🔎 الفلترة")
    all_cols = list(raw_df.columns)
    selected_cols = st.multiselect("الأعمدة المعروضة", all_cols, default=all_cols)
    filtered = raw_df.copy()

    # Offer categorical filters for columns with a manageable number of values.
    categorical_cols = [
        c for c in raw_df.columns
        if (pd.api.types.is_object_dtype(raw_df[c]) or pd.api.types.is_categorical_dtype(raw_df[c]))
        and 1 < raw_df[c].nunique(dropna=True) <= 40
    ]
    filter_cols = st.multiselect("فلترة حسب الأعمدة", categorical_cols, default=[])
    for col in filter_cols:
        values = sorted(raw_df[col].dropna().astype(str).unique().tolist())
        chosen = st.multiselect(f"القيم — {col}", values, default=values, key=f"filter_{col}")
        filtered = filtered[filtered[col].astype(str).isin(chosen)]

# Normalize dates when CSV columns look like dates.
df = filtered.copy()
for col in df.columns:
    if not pd.api.types.is_datetime64_any_dtype(df[col]) and df[col].dtype == "object":
        name_hint = any(k in str(col).lower() for k in ["date", "time", "تاريخ", "يوم"])
        if name_hint:
            parsed = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
            if parsed.notna().mean() >= 0.7:
                df[col] = parsed

num_cols = df.select_dtypes(include=np.number).columns.tolist()
date_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
cat_cols = [c for c in df.columns if c not in num_cols and c not in date_cols]
if not selected_cols:
    st.warning("اختاري عموداً واحداً على الأقل لعرضه.")
    st.stop()

# ---------- Overview ----------
st.markdown('<div class="section-title" dir="rtl">نظرة عامة</div>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("عدد السجلات بعد الفلترة", f"{len(df):,}")
with c2:
    st.metric("عدد الأعمدة", f"{len(df.columns):,}")
with c3:
    st.metric("القيم المفقودة", f"{int(df.isna().sum().sum()):,}")
with c4:
    duplicate_rows = int(df.duplicated().sum())
    st.metric("الصفوف المكررة", f"{duplicate_rows:,}")

tab1, tab2, tab3, tab4 = st.tabs(["📋 البيانات", "📈 التحليل الوصفي", "📊 الرسوم البيانية", "⬇️ التصدير"])

with tab1:
    st.markdown("#### معاينة البيانات")
    st.dataframe(df[selected_cols], use_container_width=True, height=380)
    left, right = st.columns(2)
    with left:
        st.markdown("**أنواع الأعمدة**")
        dtypes_df = pd.DataFrame({"العمود": df.columns.astype(str), "نوع البيانات": [str(x) for x in df.dtypes]})
        st.dataframe(dtypes_df, use_container_width=True, hide_index=True)
    with right:
        st.markdown("**القيم المفقودة حسب العمود**")
        missing = df.isna().sum().rename("عدد القيم المفقودة").reset_index()
        missing.columns = ["العمود", "عدد القيم المفقودة"]
        missing = missing.sort_values("عدد القيم المفقودة", ascending=False)
        st.dataframe(missing, use_container_width=True, hide_index=True)

with tab2:
    st.markdown("#### الإحصائيات الأساسية")
    if num_cols:
        desc = df[num_cols].describe().T.reset_index().rename(columns={"index": "المتغير"})
        st.dataframe(desc, use_container_width=True, hide_index=True)
        selected_num = st.selectbox("اختاري متغيراً رقمياً لملخص إضافي", num_cols)
        vals = df[selected_num].dropna()
        if len(vals):
            a, b, c, d = st.columns(4)
            a.metric("المتوسط", f"{vals.mean():,.2f}")
            b.metric("الوسيط", f"{vals.median():,.2f}")
            c.metric("الانحراف المعياري", f"{vals.std():,.2f}" if len(vals) > 1 else "—")
            d.metric("المدى", f"{vals.max()-vals.min():,.2f}")
    else:
        st.info("لم يتم العثور على أعمدة رقمية في البيانات الحالية.")
    if cat_cols:
        st.markdown("#### التوزيعات الفئوية")
        cat = st.selectbox("اختاري عموداً فئوياً", cat_cols, key="desc_cat")
        counts = df[cat].fillna("غير محدد").astype(str).value_counts().head(20).rename_axis("الفئة").reset_index(name="التكرار")
        st.dataframe(counts, use_container_width=True, hide_index=True)
    st.markdown("#### جودة البيانات")
    quality = pd.DataFrame({
        "المؤشر": ["عدد الصفوف", "عدد الأعمدة", "القيم المفقودة", "الصفوف المكررة", "نسبة اكتمال الخلايا"],
        "القيمة": [
            len(df), len(df.columns), int(df.isna().sum().sum()), duplicate_rows,
            f"{(1 - df.isna().sum().sum() / max(df.shape[0] * df.shape[1], 1))*100:.1f}%"
        ]
    })
    st.dataframe(quality, use_container_width=True, hide_index=True)

with tab3:
    st.markdown("#### إنشاء رسم بياني")
    chart_type = st.selectbox("نوع الرسم", ["Bar chart — أعمدة", "Line chart — خطي", "Pie chart — دائري", "Histogram — توزيع رقمي", "Scatter — مبعثر"])
    if chart_type.startswith("Bar"):
        if not cat_cols:
            st.info("يلزم وجود عمود فئوي للرسم بالأعمدة.")
        else:
            x_col = st.selectbox("الفئات", cat_cols, key="bar_x")
            if num_cols:
                y_col = st.selectbox("القيمة الرقمية (اختياري)", ["عدد السجلات"] + num_cols, key="bar_y")
            else:
                y_col = "عدد السجلات"
            if y_col == "عدد السجلات":
                plot_df = df[x_col].fillna("غير محدد").astype(str).value_counts().head(25).rename_axis(x_col).reset_index(name="عدد السجلات")
                fig = px.bar(plot_df, x=x_col, y="عدد السجلات", color="عدد السجلات", color_continuous_scale=["#b8d8e2", "#246a73"])
            else:
                plot_df = df.groupby(x_col, dropna=False)[y_col].mean().reset_index().sort_values(y_col, ascending=False).head(30)
                fig = px.bar(plot_df, x=x_col, y=y_col, color=y_col, color_continuous_scale=["#b8d8e2", "#246a73"])
            fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=25, b=10))
            st.plotly_chart(fig, use_container_width=True)
    elif chart_type.startswith("Line"):
        if date_cols and num_cols:
            x_col = st.selectbox("التاريخ", date_cols, key="line_date")
            y_col = st.selectbox("المتغير الرقمي", num_cols, key="line_num")
            freq = st.selectbox("تجميع الزمن", ["يومي", "شهري", "سنوي"])
            temp = df[[x_col, y_col]].dropna().copy().set_index(x_col)
            rule = {"يومي": "D", "شهري": "MS", "سنوي": "YS"}[freq]
            series = temp[y_col].resample(rule).mean().reset_index()
            fig = px.line(series, x=x_col, y=y_col, markers=True, title=f"متوسط {y_col} حسب الزمن")
            fig.update_traces(line_color="#246a73")
            fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=45, b=10))
            st.plotly_chart(fig, use_container_width=True)
        elif num_cols:
            x_col = st.selectbox("ترتيب السجلات حسب", num_cols, key="line_x")
            y_col = st.selectbox("المتغير الرقمي", num_cols, key="line_y")
            plot_df = df[[x_col, y_col]].dropna().sort_values(x_col)
            fig = px.line(plot_df, x=x_col, y=y_col, markers=True)
            fig.update_traces(line_color="#246a73")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("يلزم وجود عمود رقمي، ويفضّل وجود عمود تاريخ.")
    elif chart_type.startswith("Pie"):
        if cat_cols:
            col = st.selectbox("عمود التوزيع", cat_cols, key="pie_col")
            counts = df[col].fillna("غير محدد").astype(str).value_counts().head(12).rename_axis("الفئة").reset_index(name="العدد")
            fig = px.pie(counts, names="الفئة", values="العدد", hole=.38, color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=25, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("يلزم وجود عمود فئوي للرسم الدائري.")
    elif chart_type.startswith("Histogram"):
        if num_cols:
            col = st.selectbox("المتغير الرقمي", num_cols, key="hist_col")
            fig = px.histogram(df, x=col, nbins=25, color_discrete_sequence=["#3478a4"])
            fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=25, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("لا توجد أعمدة رقمية.")
    else:
        if len(num_cols) >= 2:
            x_col = st.selectbox("المحور X", num_cols, key="scatter_x")
            y_col = st.selectbox("المحور Y", [c for c in num_cols if c != x_col], key="scatter_y")
            color_col = st.selectbox("لون النقاط (اختياري)", ["بدون"] + cat_cols, key="scatter_color")
            fig = px.scatter(df, x=x_col, y=y_col, color=None if color_col == "بدون" else color_col,
                             hover_data=[c for c in df.columns if c not in [x_col, y_col]][:3])
            fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=25, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("يلزم وجود عمودين رقميين على الأقل.")

with tab4:
    st.markdown("#### تنزيل النتائج")
    csv_data = df[selected_cols].to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ تنزيل البيانات بعد الفلترة (CSV)", data=csv_data,
                       file_name="filtered_data.csv", mime="text/csv", use_container_width=True)
    if num_cols:
        summary = df[num_cols].describe().T
        summary_csv = summary.to_csv().encode("utf-8-sig")
        st.download_button("⬇️ تنزيل الإحصائيات الوصفية (CSV)", data=summary_csv,
                           file_name="descriptive_statistics.csv", mime="text/csv", use_container_width=True)

st.markdown("---")
st.markdown('<p class="small-note" dir="rtl">DataLens • مشروع تعليمي قابل للتطوير — تأكدي من إزالة البيانات الشخصية أو الحساسة قبل رفع الملفات إلى استضافة عامة.</p>', unsafe_allow_html=True)
