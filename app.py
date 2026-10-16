import os
import streamlit as st
import pandas as pd
import psycopg

st.set_page_config(
    page_title="Panel Bursátil & Agro | Argentina", 
    page_icon="📈", 
    layout="wide"
)

col_title, col_btn = st.columns([7, 3])
with col_title:
    st.title("📈 Panel Financierio, Energético & Agro | Argentina")
with col_btn:
    st.write("")
    if st.button("🔄 Actualizar Datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

@st.cache_data(ttl=300)
def load_data():
    db_url = os.environ.get("DATABASE_URL") or (st.secrets.get("DATABASE_URL") if hasattr(st, "secrets") else None)
    if not db_url:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    with psycopg.connect(db_url) as conn:
        df_dolar = pd.read_sql("SELECT DISTINCT ON (indicator_type) name, buy_price, sell_price, recorded_at FROM economic_indicators ORDER BY indicator_type, recorded_at DESC;", conn)
        df_fuel = pd.read_sql("SELECT DISTINCT ON (city, company, fuel_type) city, company, fuel_type, price, valid_date, recorded_at FROM fuel_prices ORDER BY city, company, fuel_type, recorded_at DESC;", conn)
        df_grains = pd.read_sql("SELECT DISTINCT ON (grain_name) grain_name, market, price_ars, price_usd, variation, recorded_at FROM grain_prices ORDER BY grain_name, recorded_at DESC;", conn)
        
    return df_dolar, df_fuel, df_grains

df_dolar, df_fuel, df_grains = load_data()

def normalize_fuel(name):
    n = str(name).upper().strip()
    if "GNC" in n: return "GNC"
    elif "SUPER" in n: return "Nafta Súper"
    elif any(k in n for k in ["INFINIA", "PREMIUM", "V-POWER", "VPOWER", "QUANTIUM"]): return "Nafta Premium"
    elif any(k in n for k in ["DIESEL500", "DIESEL 500", "ULTRA", "AXION DIESEL", "PUMA DIESEL", "DIESEL COMUN"]): return "Gasoil Común"
    elif any(k in n for k in ["INFINIA DIESEL", "ION", "EURO", "V-POWER DIESEL", "QUANTIUM DIESEL"]): return "Gasoil Premium"
    else: return name

tab1, tab2, tab3 = st.tabs(["💱 Dólares", "⛽ Combustibles", "🌾 Agro (Granos)"])

with tab1:
    if df_dolar.empty:
        st.info("Sin registros de dólares.")
    else:
        df_d = df_dolar[["name", "buy_price", "sell_price", "recorded_at"]].copy()
        df_d.columns = ["Indicador", "Compra ($)", "Venta ($)", "Actualización"]
        df_d["Compra ($)"] = df_d["Compra ($)"].apply(lambda x: f"${x:,.2f}" if pd.notnull(x) else "-")
        df_d["Venta ($)"] = df_d["Venta ($)"].apply(lambda x: f"${x:,.2f}" if pd.notnull(x) else "-")
        st.dataframe(df_d, hide_index=True, use_container_width=True)

with tab2:
    if df_fuel.empty:
        st.info("Sin registros de combustibles.")
    else:
        ciudades = sorted(df_fuel["city"].unique())
        default_idx = ciudades.index("SANTA FE") if "SANTA FE" in ciudades else 0
        selected_city = st.selectbox("Seleccionar Ciudad / Capital:", ciudades, index=default_idx)
        
        df_f = df_fuel[df_fuel["city"] == selected_city].copy()
        df_f["fuel_category"] = df_f["fuel_type"].apply(normalize_fuel)
        
        pivot_fuel = df_f.pivot_table(index="fuel_category", columns="company", values="price", aggfunc="first").reset_index()
        for col in pivot_fuel.columns:
            if col != "fuel_category":
                pivot_fuel[col] = pivot_fuel[col].apply(lambda x: f"${x:,.2f}" if pd.notnull(x) else "-")
        pivot_fuel = pivot_fuel.rename(columns={"fuel_category": "Combustible"})
        
        st.markdown(f"**Precios en {selected_city}**")
        st.dataframe(pivot_fuel, hide_index=True, use_container_width=True)

with tab3:
    st.subheader("🌾 Pizarra de Granos (Zona Rosario / Disponible)")
    if df_grains.empty:
        st.info("Todavía no hay datos de granos recolectados. Ejecutá el workflow en GitHub Actions.")
    else:
        df_g = df_grains.copy()
        df_g.columns = ["Grano", "Mercado", "Precio ($/TN)", "Precio (USD/TN)", "Variación (%)", "Actualización"]
        df_g["Precio ($/TN)"] = df_g["Precio ($/TN)"].apply(lambda x: f"${x:,.2f}" if pd.notnull(x) else "-")
        df_g["Precio (USD/TN)"] = df_g["Precio (USD/TN)"].apply(lambda x: f"US${x:,.2f}" if pd.notnull(x) else "-")
        df_g["Variación (%)"] = df_g["Variación (%)"].apply(lambda x: f"{x:+.2f}%" if pd.notnull(x) else "-")
        
        st.dataframe(df_g, hide_index=True, use_container_width=True)
