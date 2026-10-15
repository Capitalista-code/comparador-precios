import os
import streamlit as st
import pandas as pd
import psycopg

st.set_page_config(page_title="Indicadores Argentina", page_icon="📈", layout="wide")

st.title("📊 Panel de Indicadores Económicos - Argentina")
st.markdown("Cotizaciones en tiempo real actualizadas desde Supabase.")

def load_data():
    db_url = os.environ.get("DATABASE_URL") or st.secrets.get("DATABASE_URL") if hasattr(st, "secrets") else None
    if not db_url:
        st.error("No se encontró la variable DATABASE_URL.")
        return pd.DataFrame()
    
    query = """
        SELECT DISTINCT ON (indicator_type) 
            name, buy_price, sell_price, recorded_at
        FROM economic_indicators
        ORDER BY indicator_type, recorded_at DESC;
    """
    with psycopg.connect(db_url) as conn:
        df = pd.read_sql(query, conn)
    return df

df = load_data()

if df.empty:
    st.warning("Todavía no hay datos guardados. Ejecutá el recolector en GitHub Actions.")
else:
    st.subheader("💱 Cotizaciones de Dólares")
    cols = st.columns(3)
    
    for index, row in df.iterrows():
        col = cols[index % 3]
        with col:
            st.metric(
                label=row["name"],
                value=f"${row['sell_price']}" if pd.notnull(row['sell_price']) else "N/D",
                delta=f"Compra: ${row['buy_price']}" if pd.notnull(row['buy_price']) else None
            )
            st.caption(f"Actualizado: {row['recorded_at']}")

    if st.button("🔄 Actualizar datos"):
        st.rerun()
