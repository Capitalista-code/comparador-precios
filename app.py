import os
import streamlit as st
import pandas as pd
import psycopg

st.set_page_config(page_title="Indicadores Argentina", page_icon="📈", layout="wide")

st.title("📊 Panel de Indicadores Económicos y Combustibles - Argentina")
st.markdown("Cotizaciones de dólares y precios de naftas en tiempo real actualizadas desde Supabase.")

def load_data():
    db_url = os.environ.get("DATABASE_URL") or (st.secrets.get("DATABASE_URL") if hasattr(st, "secrets") else None)
    if not db_url:
        st.error("No se encontró la variable DATABASE_URL.")
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

tab1, tab2 = st.tabs(["💱 Dólares", "⛽ Combustibles"])

with tab1:
    st.subheader("Cotizaciones de Dólares")
    if df_dolar.empty:
        st.warning("No hay datos de dólares guardados todavía.")
    else:
        cols = st.columns(3)
        for index, row in df_dolar.iterrows():
            col = cols[index % 3]
            with col:
                st.metric(
                    label=row["name"],
                    value=f"${row['sell_price']}" if pd.notnull(row['sell_price']) else "N/D",
                    delta=f"Compra: ${row['buy_price']}" if pd.notnull(row['buy_price']) else None
                )
                st.caption(f"Actualizado: {row['recorded_at']}")

with tab2:
    st.subheader("Precios de Combustibles por Ciudad y Bandera")
    if df_fuel.empty:
        st.warning("No hay datos de combustibles guardados todavía. Ejecutá el recolector en GitHub Actions.")
    else:
        ciudades = df_fuel["city"].unique()
        default_idx = list(ciudades).index("SANTA FE") if "SANTA FE" in ciudades else 0
        selected_city = st.selectbox("Seleccioná la Ciudad:", ciudades, index=default_idx)
        
        df_filtered = df_fuel[df_fuel["city"] == selected_city]
        
        empresas = df_filtered["company"].unique()
        for emp in empresas:
            st.markdown(f"### ⛽ {emp}")
            df_emp = df_filtered[df_filtered["company"] == emp]
            
            st.dataframe(
                df_emp[["fuel_type", "price", "valid_date"]].rename(
                    columns={"fuel_type": "Combustible", "price": "Precio ($)", "valid_date": "Vigencia"}
                ),
                hide_index=True,
                use_container_width=True
            )

if st.button("🔄 Actualizar datos"):
    st.rerun()
