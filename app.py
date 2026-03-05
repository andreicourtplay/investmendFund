import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st


# -----------------------------
# Config
# -----------------------------
st.set_page_config(
    page_title="Funds Weekly Dashboard",
    page_icon="📊",
    layout="wide",
)


# -----------------------------
# Estilos (cards + look)
# -----------------------------
st.markdown(
    """
    <style>
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
    .title { font-size: 2rem; font-weight: 800; letter-spacing: 0.5px; }
    .subtitle { color: #9aa0a6; margin-top: -10px; }

    .kpi-card {
        border: 1px solid rgba(255,255,255,0.08);
        background: linear-gradient(180deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%);
        border-radius: 18px;
        padding: 16px 18px;
        box-shadow: 0 8px 26px rgba(0,0,0,0.25);
    }
    .kpi-label { font-size: 0.85rem; color: rgba(255,255,255,0.70); }
    .kpi-value { font-size: 1.65rem; font-weight: 800; margin-top: 6px; }
    .kpi-sub { font-size: 0.80rem; color: rgba(255,255,255,0.55); margin-top: 6px; }
    .pill {
        display:inline-block;
        padding: 6px 10px;
        border-radius: 999px;
        font-size: 0.8rem;
        border: 1px solid rgba(255,255,255,0.12);
        background: rgba(255,255,255,0.04);
        color: rgba(255,255,255,0.80);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------
# Paths / constants
# -----------------------------
DATA_DIR = Path("data")
PUBLISHED_DATA_FILE = DATA_DIR / "published_data.csv"
PUBLISHED_META_FILE = DATA_DIR / "published_meta.json"

EXPECTED_COLS = [
    "Week",
    "Fecha Act",
    "SumaDeBEGINNER NAV",
    "SumaDeCLOSE TRADE",
    "SumaDeNET LIQUID VALUE",
    "SumaDeLIQUIDACION",
    "SumaDeCASH NAV",
    "SumaDeOPEN CASH FLOW",
    "SumaDeFREE CASH",
    "SumaDeTRADING",
    "Fondo",
    "CloseTrade_BRUTO",
]

NUMERIC_COLS = [
    "SumaDeBEGINNER NAV",
    "SumaDeCLOSE TRADE",
    "SumaDeNET LIQUID VALUE",
    "SumaDeLIQUIDACION",
    "SumaDeCASH NAV",
    "SumaDeOPEN CASH FLOW",
    "SumaDeFREE CASH",
    "SumaDeTRADING",
    "CloseTrade_BRUTO",
]


# -----------------------------
# Helpers
# -----------------------------
def get_admin_password() -> str:
    password = ""
    try:
        password = str(st.secrets.get("ADMIN_PASSWORD", ""))
    except Exception:
        password = ""
    if not password:
        password = os.getenv("FUNDS_ADMIN_PASSWORD", "")
    return password.strip()


def format_money(x) -> str:
    if pd.isna(x):
        return "—"
    try:
        return f"${x:,.0f}"
    except Exception:
        return str(x)


def format_published_at(iso_value: str) -> str:
    if not iso_value:
        return "—"
    dt = pd.to_datetime(iso_value, errors="coerce", utc=True)
    if pd.isna(dt):
        return str(iso_value)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def normalize_df(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    df = df.copy()

    # Normaliza nombres (por si hay espacios raros)
    df.columns = [str(c).strip() for c in df.columns]

    # Si no existe "Fondo", intenta inferirlo
    if "Fondo" not in df.columns:
        upper = source_name.upper()
        if "ESP" in upper:
            df["Fondo"] = "ESP"
        elif "INCUB" in upper:
            df["Fondo"] = "INCUBATOR"
        elif "INSTITUTE" in upper or "INS" in upper:
            df["Fondo"] = "INSTITUTE"
        else:
            df["Fondo"] = "UNKNOWN"

    # Fecha
    if "Fecha Act" in df.columns:
        df["Fecha Act"] = pd.to_datetime(df["Fecha Act"], errors="coerce")
    else:
        df["Fecha Act"] = pd.NaT

    # Asegura columnas numéricas
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # CloseTrade_BRUTO: fallback si viene vacío
    if "CloseTrade_BRUTO" not in df.columns:
        df["CloseTrade_BRUTO"] = pd.NA

    # Si CloseTrade_BRUTO está todo vacío, usa SumaDeCLOSE TRADE como proxy
    if df["CloseTrade_BRUTO"].isna().all() and "SumaDeCLOSE TRADE" in df.columns:
        df["CloseTrade_BRUTO"] = df["SumaDeCLOSE TRADE"]

    # Solo para trazabilidad interna
    df["__source__"] = source_name

    keep = [c for c in EXPECTED_COLS if c in df.columns] + ["__source__"]
    return df[keep]


def clean_all_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if "Fecha Act" in out.columns:
        out["Fecha Act"] = pd.to_datetime(out["Fecha Act"], errors="coerce")
    else:
        out["Fecha Act"] = pd.NaT

    for col in NUMERIC_COLS:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    if "__source__" in out.columns:
        # Evita exponer nombres de archivos en el dataset publicado.
        out = out.drop(columns=["__source__"])

    if "Fondo" not in out.columns:
        out["Fondo"] = "UNKNOWN"

    out = out.dropna(subset=["Fondo"])
    out["Fondo"] = out["Fondo"].astype(str).str.strip()
    out = out[out["Fondo"] != ""]

    return out


@st.cache_data(show_spinner=False)
def read_any_file(file) -> pd.DataFrame:
    name = getattr(file, "name", "uploaded_file")
    suffix = Path(name).suffix.lower()

    if suffix in [".xlsx", ".xls"]:
        df = pd.read_excel(file, sheet_name=0)
        return normalize_df(df, name)

    if suffix == ".csv":
        try:
            df = pd.read_csv(file)
        except Exception:
            df = pd.read_csv(file, sep=";")
        return normalize_df(df, name)

    raise ValueError(f"Formato no soportado: {suffix}")


def parse_uploaded_files(uploaded_files) -> Tuple[pd.DataFrame, List[Tuple[str, str]]]:
    dfs: List[pd.DataFrame] = []
    errors: List[Tuple[str, str]] = []
    for file in uploaded_files:
        try:
            dfs.append(read_any_file(file))
        except Exception as exc:
            errors.append((getattr(file, "name", "file"), str(exc)))

    if not dfs:
        return pd.DataFrame(), errors

    merged = pd.concat(dfs, ignore_index=True)
    merged = clean_all_df(merged)
    return merged, errors


def save_published_data(df: pd.DataFrame, uploaded_count: int) -> None:
    clean_df = clean_all_df(df)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    clean_df.to_csv(PUBLISHED_DATA_FILE, index=False)

    meta = {
        "published_at": datetime.now(timezone.utc).isoformat(),
        "rows": int(len(clean_df)),
        "funds": int(clean_df["Fondo"].nunique()) if "Fondo" in clean_df.columns else 0,
        "uploaded_files": int(uploaded_count),
    }
    PUBLISHED_META_FILE.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_published_data() -> Tuple[pd.DataFrame, Dict]:
    if not PUBLISHED_DATA_FILE.exists():
        return pd.DataFrame(), {}

    try:
        data = pd.read_csv(PUBLISHED_DATA_FILE)
    except Exception:
        return pd.DataFrame(), {}

    meta: Dict = {}
    if PUBLISHED_META_FILE.exists():
        try:
            meta = json.loads(PUBLISHED_META_FILE.read_text(encoding="utf-8"))
        except Exception:
            meta = {}

    data = clean_all_df(data)
    return data, meta


def last_week_per_fund(all_df: pd.DataFrame) -> pd.DataFrame:
    tmp = all_df.dropna(subset=["Fecha Act"]).copy()
    if tmp.empty:
        return tmp
    idx = tmp.sort_values("Fecha Act").groupby("Fondo")["Fecha Act"].idxmax()
    return tmp.loc[idx].sort_values("Fondo")


def render_kpi(label: str, value, sub: str = ""):
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------
# Session state
# -----------------------------
if "is_admin" not in st.session_state:
    st.session_state["is_admin"] = False

flash_message = st.session_state.pop("flash_message", "")
if flash_message:
    st.success(flash_message)


# -----------------------------
# UI - Header
# -----------------------------
st.markdown('<div class="title">📊 Funds Weekly Dashboard</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Vista pública de datos ya publicados. Solo admin puede subir nuevos archivos.</div>',
    unsafe_allow_html=True,
)


# -----------------------------
# Sidebar - Auth / Publish / View
# -----------------------------
admin_password = get_admin_password()
admin_auth_enabled = bool(admin_password)
is_admin = st.session_state.get("is_admin", False)
can_upload = is_admin or not admin_auth_enabled

uploaded_files = []
publish_clicked = False

with st.sidebar:
    st.header("🔐 Acceso")
    if admin_auth_enabled:
        if is_admin:
            st.success("Modo admin activo")
            if st.button("Salir de admin", use_container_width=True):
                st.session_state["is_admin"] = False
                st.rerun()
        else:
            candidate = st.text_input("Password admin", type="password")
            if st.button("Entrar como admin", use_container_width=True):
                if candidate == admin_password:
                    st.session_state["is_admin"] = True
                    st.rerun()
                else:
                    st.error("Password incorrecta.")
    else:
        st.warning(
            "No hay ADMIN_PASSWORD configurada. Cualquiera con el link puede publicar datos."
        )

    st.divider()
    st.subheader("⚙️ Vista")
    n_weeks = st.slider(
        "Semanas para gráfico", min_value=4, max_value=52, value=16, step=4
    )

    if can_upload:
        st.divider()
        st.subheader("📥 Publicar datos")
        uploaded_files = st.file_uploader(
            "Sube uno o varios archivos (CSV / XLSX)",
            type=["csv", "xlsx", "xls"],
            accept_multiple_files=True,
            key="publish_uploader",
        )
        publish_clicked = st.button(
            "Publicar dataset",
            disabled=not uploaded_files,
            use_container_width=True,
        )


# -----------------------------
# Publish flow (admin only)
# -----------------------------
publish_errors: List[Tuple[str, str]] = []
if can_upload and publish_clicked:
    fresh_df, publish_errors = parse_uploaded_files(uploaded_files)
    if fresh_df.empty:
        st.error("No se pudo publicar: no hay filas válidas en los archivos.")
    else:
        save_published_data(fresh_df, len(uploaded_files))
        st.session_state["flash_message"] = (
            f"Datos publicados correctamente ({len(fresh_df)} filas)."
        )
        st.rerun()

if publish_errors:
    with st.expander("⚠️ Archivos con error al publicar"):
        for name, err in publish_errors:
            st.write(f"**{name}** → {err}")


# -----------------------------
# Load published dataset
# -----------------------------
all_df, published_meta = load_published_data()
if all_df.empty:
    if can_upload:
        st.info("Aún no hay datos publicados. Sube archivos y pulsa 'Publicar dataset'.")
    else:
        st.info("No hay datos publicados todavía. Pide al administrador que publique.")
    st.stop()

latest_df = last_week_per_fund(all_df)
if latest_df.empty:
    st.error("No hay filas con 'Fecha Act' válida en el dataset publicado.")
    st.stop()


# -----------------------------
# Top selector
# -----------------------------
funds = sorted(latest_df["Fondo"].unique().tolist())
col_a, col_b, col_c = st.columns([2, 2, 2])
with col_a:
    selected_fund = st.selectbox("Fondo", funds, index=0)
with col_b:
    last_date = latest_df.loc[latest_df["Fondo"] == selected_fund, "Fecha Act"].iloc[0]
    st.markdown(
        f"<span class='pill'>Última fecha: <b>{last_date.date().isoformat()}</b></span>",
        unsafe_allow_html=True,
    )
with col_c:
    stamp = format_published_at(str(published_meta.get("published_at", "")))
    st.markdown(
        f"<span class='pill'>Publicado: <b>{stamp}</b></span>",
        unsafe_allow_html=True,
    )

selected_latest = latest_df[latest_df["Fondo"] == selected_fund].iloc[0]


# -----------------------------
# KPI Grid (Cards)
# -----------------------------
k1, k2, k3 = st.columns(3)
with k1:
    render_kpi(
        "Beginner NAV",
        format_money(selected_latest.get("SumaDeBEGINNER NAV")),
        "Valor inicial de la semana",
    )
with k2:
    render_kpi(
        "Net Liquid Value",
        format_money(selected_latest.get("SumaDeNET LIQUID VALUE")),
        "Valor liquidativo neto",
    )
with k3:
    render_kpi(
        "Cash NAV",
        format_money(selected_latest.get("SumaDeCASH NAV")),
        "Caja / NAV en efectivo",
    )

k4, k5, k6 = st.columns(3)
with k4:
    render_kpi(
        "Suma Close Trade",
        format_money(selected_latest.get("SumaDeCLOSE TRADE")),
        "Close trades (semana)",
    )
with k5:
    render_kpi(
        "Free Cash Disponible",
        format_money(selected_latest.get("SumaDeFREE CASH")),
        "Efectivo libre",
    )
with k6:
    render_kpi(
        "Close Trade Bruto",
        format_money(selected_latest.get("CloseTrade_BRUTO")),
        "Gross close trade performance (proxy)",
    )


# -----------------------------
# Tabla última semana
# -----------------------------
st.markdown("### 🧾 Última semana (detalle)")
table_cols = [
    "Fondo",
    "Week",
    "Fecha Act",
    "SumaDeBEGINNER NAV",
    "SumaDeCLOSE TRADE",
    "CloseTrade_BRUTO",
    "SumaDeNET LIQUID VALUE",
    "SumaDeCASH NAV",
    "SumaDeFREE CASH",
    "SumaDeOPEN CASH FLOW",
    "SumaDeTRADING",
    "SumaDeLIQUIDACION",
]
existing = [col for col in table_cols if col in latest_df.columns]
pretty = latest_df.copy()

for col in [x for x in existing if x in NUMERIC_COLS]:
    pretty[col] = pretty[col].apply(lambda v: f"{v:,.0f}" if pd.notna(v) else "")

st.dataframe(
    pretty[existing].sort_values("Fondo"),
    use_container_width=True,
    hide_index=True,
)


# -----------------------------
# Evolución últimas N semanas (gráficos)
# -----------------------------
st.markdown("### 📈 Evolución (últimas semanas)")
df_f = (
    all_df[all_df["Fondo"] == selected_fund]
    .dropna(subset=["Fecha Act"])
    .sort_values("Fecha Act")
)
df_f = df_f.tail(n_weeks)

c1, c2 = st.columns(2)

with c1:
    st.markdown("**Net Liquid Value**")
    if "SumaDeNET LIQUID VALUE" in df_f.columns:
        st.line_chart(df_f.set_index("Fecha Act")["SumaDeNET LIQUID VALUE"])
    else:
        st.info("No existe columna 'SumaDeNET LIQUID VALUE' en este fondo.")

with c2:
    st.markdown("**Cash / Free Cash**")
    cols = []
    if "SumaDeCASH NAV" in df_f.columns:
        cols.append("SumaDeCASH NAV")
    if "SumaDeFREE CASH" in df_f.columns:
        cols.append("SumaDeFREE CASH")
    if cols:
        st.line_chart(df_f.set_index("Fecha Act")[cols])
    else:
        st.info("No existen columnas de Cash para este fondo.")

st.caption(
    "Tip: configura ADMIN_PASSWORD para que solo tú puedas publicar y compartir el link en modo lectura."
)
