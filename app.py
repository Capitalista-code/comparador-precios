import os
import streamlit as st
import pandas as pd
import psycopg

# Configuración inicial de la página (ancho completo, compacto)
st.set_page_config(
    page_title="Panel Bursátil & Energético - Argentina", 
    page_icon="📈", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Estilos CSS estilo Ráva / Terminal Financiera (minimalista, denso, bordes finos)
st.markdown("""
    <style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        padding-left: 2rem;
        padding-right: 2rem;
    }
    h1, h2, h3 {
        letter-spacing: -0.5px;
    }
    .stDataFrame {
        border: 1px solid #2b2b2b;
        border-radius: 4px;
    }
    </style>
""", unsafe_allow_html=True)

# Título y barra superior minimalista
col_title, col_btn = st.columns([8, 2])
with col_title:
    st.markdown("### 📈 Panel Financiero & Energético | Argentina")
with col_btn:
    if st.button("🔄 Actualizar", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown("<hr style='margin: 0.2rem 0 1rem 0; border-color: #333;'>", unsafe_allow_html=True)

# Conexión y carga de datos con caché
@st.cache_data(ttl=300)
def load_data():
    db_url = os.environ.get("DATABASE_URL") or (st.secrets.get("DATABASE_URL") if hasattr(st, "secrets") else None)
    if not db_url:
        return pd.DataFrame(), pd.DataFrame()
    
    query_dolar = """
        SELECT DISTINCT ON (indicator_type) 
            name, buy_price, sell_price, recorded_at
        FROM economic_indicators
        ORDER BY indicator_type, recorded_at DESC;
    """
    
    query_fuel = """
        SELECT DISTINCT ON (city, company, fuel_type) 
            city, company, fuel_type, price, valid_date, recorded_at
        FROM fuel_prices
        ORDER BY city, company, fuel_type, recorded_at DESC;
    """
    
    with psycopg.connect(db_url) as conn:
        df_dolar = pd.read_sql(query_dolar, conn)
        df_fuel = pd.read_sql(query_fuel, conn)
        
    return df_dolar, df_fuel

df_dolar, df_fuel = load_data()

# Pestañas limpias estilo panel
tab1, tab2 = st.tabs(["💱 Cotizaciones de Dólares", "⛽ Matriz de Combustibles"])

with tab1:
    if df_dolar.empty:
        st.info("No hay cotizaciones de dólares registradas.")
    else:
        df_dolar_clean = df_dolar[["name", "buy_price", "sell_price", "recorded_at"]].copy()
        df_dolar_clean.columns = ["Indicador", "Compra ($)", "Venta ($)", "Última Actualización"]
        df_dolar_clean["Compra ($)"] = df_dolar_clean["Compra ($)"].apply(lambda x: f"${x:,.2f}" if pd.notnull(x) else "-")
        df_dolar_clean["Venta ($)"] = df_dolar_clean["Venta ($)"].apply(lambda x: f"${x:,.2f}" if pd.notnull(x) else "-")
        
        st.dataframe(
            df_dolar_clean,
            hide_index=True,
            use_container_width=True
        )

with tab2:
    if df_fuel.empty:
        st.info("No hay precios de combustibles registrados. Ejecutá el recolector en GitHub Actions.")
    else:
        ciudades = sorted(df_fuel["city"].unique())
        default_idx = ciudades.index("SANTA FE") if "SANTA FE" in ciudades else 0
        
        c1, c2 = st.columns([3, 7])
        with c1:
            selected_city = st.selectbox("Seleccionar Ciudad:", ciudades, index=default_idx)
        
        df_filtered = df_fuel[df_fuel["city"] == selected_city]
        
        if df_filtered.empty:
            st.warning(f"Sin datos para {selected_city}.")
        else:
            # Matriz cruzada (Combustibles en filas, Marcas en columnas estilo Ráva)
            pivot_fuel = df_filtered.pivot_table(
                index="fuel_type", 
                columns="company", 
                values="price", 
                aggfunc="first"
            ).reset_index()
            
            for col in pivot_fuel.columns:
                if col != "fuel_type":
                    pivot_fuel[col] = pivot_fuel[col].apply(lambda x: f"${x:,.2f}" if pd.notnull(x) else "-")
            
            pivot_fuel = pivot_fuel.rename(columns={"fuel_type": "Combustible"})
            
            st.markdown(f"**Precios en {selected_city}**")
            st.dataframe(
                pivot_fuel,
                hide_index=True,
                use_container_width=True
            )
