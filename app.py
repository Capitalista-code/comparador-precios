import os
import streamlit as st
import pandas as pd
import psycopg

# Configuración inicial de la página
st.set_page_config(
    page_title="Indicadores Argentina", 
    page_icon="🇦🇷", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados para darle un toque moderno
st.markdown("""
    <style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .metric-card {
        background-color: #1e2129;
        border: 1px solid #2d3139;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin-bottom: 15px;
    }
    h1 {
        color: #fafafa;
        font-weight: 700;
    }
    </style>
""", unsafe_allow_html=True)

# Título Principal
st.title("🇦🇷 Panel Económico & Energético")
st.markdown("Cotizaciones del dólar y precios de combustibles actualizados en tiempo real desde Supabase.")
st.divider()

# Conexión y carga de datos
@st.cache_data(ttl=600)
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

# Sidebar con opciones y estado
with st.sidebar:
    st.header("⚙️ Controles")
    if st.button("🔄 Actualizar Datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    st.info("💡 **Tip:** Los datos de combustibles se actualizan automáticamente mediante GitHub Actions.")
    st.markdown("Desarrollado con **Streamlit**, **Supabase** y **Python**.")

# Pestañas principales
tab1, tab2 = st.tabs(["💱 Cotizaciones de Dólares", "⛽ Precios de Combustibles"])

with tab1:
    st.subheader("💱 Dólar en Argentina")
    if df_dolar.empty:
        st.warning("No hay datos de dólares guardados todavía.")
    else:
        cols = st.columns(3)
        for index, row in df_dolar.iterrows():
            col = cols[index % 3]
            with col:
                sell_val = f"\${row['sell_price']:,.2f}" if pd.notnull(row['sell_price']) else "N/D"
                buy_val = f"Compra: \${row['buy_price']:,.2f}" if pd.notnull(row['buy_price']) else "Compra: N/D"
                
                st.metric(
                    label=row["name"],
                    value=sell_val,
                    delta=buy_val
                )
                st.caption(f"Actualizado: {row['recorded_at']}")
                st.markdown("---")

with tab2:
    st.subheader("⛽ Estación de Precios por Provincia")
    if df_fuel.empty:
        st.warning("No hay datos de combustibles guardados todavía.")
    else:
        ciudades = sorted(df_fuel["city"].unique())
        default_idx = ciudades.index("SANTA FE") if "SANTA FE" in ciudades else 0
        
        selected_city = st.selectbox("🏙️ Seleccioná la Capital / Ciudad:", ciudades, index=default_idx)
        
        df_filtered = df_fuel[df_fuel["city"] == selected_city]
        empresas = sorted(df_filtered["company"].unique())
        
        if not empresas:
            st.info(f"No hay registros de combustibles para {selected_city}.")
        else:
            cols_emp = st.columns(min(len(empresas), 3))
            for i, emp in enumerate(empresas):
                col = cols_emp[i % len(cols_emp)]
                with col:
                    st.markdown(f"### ⛽ {emp}")
                    df_emp = df_filtered[df_filtered["company"] == emp]
                    
                    for _, row in df_emp.iterrows():
                        precio_str = f"\${row['price']:,.2f}" if pd.notnull(row['price']) else "N/D"
                        st.markdown(f"**{row['fuel_type']}**: `{precio_str}`")
                    st.markdown("---")
