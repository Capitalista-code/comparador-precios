import os
import streamlit as st
import pandas as pd
import psycopg

# Configuración inicial de la página
st.set_page_config(
    page_title="Panel Bursátil & Energético - Argentina", 
    page_icon="📈", 
    layout="wide"
)

# Encabezado limpio y visible sin cortes
col_title, col_btn = st.columns([7, 3])
with col_title:
    st.title("📈 Panel Financiero & Energético | Argentina")
with col_btn:
    st.write("") # Espaciador de alineación
    if st.button("🔄 Actualizar Datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

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

# Función para unificar los nombres comerciales de los combustibles entre marcas
def normalize_fuel(name):
    n = str(name).upper().strip()
    if "GNC" in n:
        return "GNC"
    elif "SUPER" in n:
        return "Nafta Súper"
    elif any(k in n for k in ["INFINIA", "PREMIUM", "V-POWER", "VPOWER", "QUANTIUM"]):
        return "Nafta Premium"
    elif any(k in n for k in ["DIESEL500", "DIESEL 500", "ULTRA", "AXION DIESEL", "PUMA DIESEL", "DIESEL COMUN"]):
        return "Gasoil Común (Grado 2)"
    elif any(k in n for k in ["INFINIA DIESEL", "ION", "EURO", "V-POWER DIESEL", "QUANTIUM DIESEL"]):
        return "Gasoil Premium (Grado 3)"
    else:
        return name

# Pestañas principales
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
            selected_city = st.selectbox("Seleccionar Ciudad / Capital:", ciudades, index=default_idx)
        
        df_filtered = df_fuel[df_fuel["city"] == selected_city].copy()
        
        if df_filtered.empty:
            st.warning(f"Sin datos para {selected_city}.")
        else:
            # Aplicamos la categoría unificada
            df_filtered["fuel_category"] = df_filtered["fuel_type"].apply(normalize_fuel)
            
            # Creamos la matriz cruzada limpia y ordenada
            pivot_fuel = df_filtered.pivot_table(
                index="fuel_category", 
                columns="company", 
                values="price", 
                aggfunc="first"
            ).reset_index()
            
            for col in pivot_fuel.columns:
                if col != "fuel_category":
                    pivot_fuel[col] = pivot_fuel[col].apply(lambda x: f"${x:,.2f}" if pd.notnull(x) else "-")
            
            pivot_fuel = pivot_fuel.rename(columns={"fuel_category": "Combustible"})
            
            st.markdown(f"**Comparativa de Precios en {selected_city}**")
            st.dataframe(
                pivot_fuel,
                hide_index=True,
                use_container_width=True
            )
