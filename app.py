import os
import streamlit as st
import pandas as pd
import psycopg

# Configuración inicial con sidebar expandido y diseño responsive
st.set_page_config(
    page_title="Terminal Financiera & Agro | Argentina", 
    page_icon="📈", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS avanzados: Estilo granos.ar + Rava Bursátil + Optimización Mobile
st.markdown("""
<style>
    /* Estilo de la barra lateral (Estilo Granos.ar) */
    section[data-testid="stSidebar"] {
        background-color: #fcfbfa;
        border-right: 1px solid #e7e2d9;
    }
    
    /* Grilla de tarjetas adaptable a celulares */
    .dollar-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 12px;
        margin-top: 10px;
        margin-bottom: 25px;
    }
    
    @media (max-width: 640px) {
        .dollar-grid {
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
        }
    }

    .dollar-card {
        background-color: #faf8f5;
        border: 1px solid #e7e2d9;
        border-radius: 6px;
        padding: 12px 14px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.01);
    }
    
    .card-blue { border-top: 3px solid #3b82f6; }
    .card-green { border-top: 3px solid #10b981; }
    .card-purple { border-top: 3px solid #8b5cf6; }
    .card-indigo { border-top: 3px solid #6366f1; }
    .card-amber { border-top: 3px solid #d97706; }
    .card-gray { border-top: 3px solid #78716c; }

    .dollar-title {
        font-size: 10px;
        font-weight: 700;
        color: #78716c;
        letter-spacing: 0.4px;
        margin-bottom: 4px;
        text-transform: uppercase;
    }
    .dollar-price {
        font-size: 19px;
        font-weight: 700;
        color: #1c1917;
        margin-bottom: 4px;
    }
    .dollar-range {
        font-size: 10px;
        color: #8c857b;
    }

    /* Estilo Rava Bursátil para tablas de datos */
    .dataframe {
        font-size: 13px !important;
    }
</style>
""", unsafe_allow_html=True)

# Carga de datos con caché
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

# ==========================================
# MENÚ LATERAL (SIDEBAR) ESTILO GRANOS.AR
# ==========================================
with st.sidebar:
    st.markdown("<p style='font-size: 10px; color: #78716c; font-weight: 700; margin-bottom:0;'>AGRO • FINANZAS • ARGENTINA</p>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-top: 0; color: #1c1917;'>Terminal.ar</h2>", unsafe_allow_html=True)
    st.markdown("<p style='font-size: 11px; color: #10b981; margin-bottom: 10px;'>🟢 Sistema Conectado</p>", unsafe_allow_html=True)
    
    if st.button("🔄 Actualizar Datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown("<p style='font-size: 10px; color: #78716c; font-weight: 700; letter-spacing: 0.5px;'>NAVEGACIÓN</p>", unsafe_allow_html=True)
    
    seleccion_actual = st.radio(
        "Secciones",
        [
            "📊 Resumen del Día", 
            "💱 Dólares", 
            "🌾 Precios Pizarra", 
            "⛽ Combustibles"
        ],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    st.markdown("<p style='font-size: 9px; color: #a8a29e;'>Terminal Profesional v2.0</p>", unsafe_allow_html=True)

# ==========================================
# RENDERIZADO DE TARJETAS DE DÓLAR (ESTILO COMPACTO)
# ==========================================
def render_dollar_cards(df):
    if df.empty:
        st.info("Sin registros de dólares.")
        return

    cards_html = '<div class="dollar-grid">'
    
    def get_accent(name):
        n = str(name).lower()
        if 'blue' in n: return 'card-blue'
        if 'oficial' in n or 'banco nación' in n: return 'card-green'
        if 'mep' in n or 'bolsa' in n: return 'card-purple'
        if 'ccl' in n or 'contado' in n: return 'card-indigo'
        if 'tarjeta' in n: return 'card-amber'
        return 'card-gray'

    for _, row in df.iterrows():
        nombre = row.get('name', 'Dólar')
        venta = row.get('sell_price', 0)
        compra = row.get('buy_price', 0)
        
        str_venta = f"\${venta:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notnull(venta) else "-"
        str_compra = f"\${compra:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notnull(compra) else "-"
        
        accent = get_accent(nombre)
        cards_html += f'<div class="dollar-card {accent}"><div class="dollar-title">{nombre}</div><div class="dollar-price">{str_venta}</div><div class="dollar-range">C: {str_compra} / V: {str_venta}</div></div>'
        
    cards_html += '</div>'
    st.markdown(cards_html, unsafe_allow_html=True)

# ==========================================
# VISTAS SEGÚN MENÚ
# ==========================================

if "Resumen" in seleccion_actual:
    st.markdown("### 📊 Resumen General del Día")
    st.markdown("<p style='font-size: 12px; color: #78716c;'>Panel integrado de cotizaciones y referencias de mercado.</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    st.markdown("##### 💱 Divisas & Dólares")
    render_dollar_cards(df_dolar)
    
    st.markdown("##### 🌾 Pizarra de Granos (Referencia Rosario)")
    if not df_grains.empty:
        df_g = df_grains.copy()
        df_g.columns = ["Grano", "Mercado", "Precio (\$/TN)", "Precio (USD/TN)", "Variación (%)", "Actualización"]
        df_g["Precio ($/TN)"] = df_g["Precio ($/TN)"].apply(lambda x: f"\${x:,.2f}" if pd.notnull(x) else "-")
        df_g["Precio (USD/TN)"] = df_g["Precio (USD/TN)"].apply(lambda x: f"US\${x:,.2f}" if pd.notnull(x) else "-")
        df_g["Variación (%)"] = df_g["Variación (%)"].apply(lambda x: f"{x:+.2f}%" if pd.notnull(x) else "-")
        st.dataframe(df_g, hide_index=True, use_container_width=True)
    else:
        st.info("Sin datos de granos cargados.")

elif "Dólares" in seleccion_actual:
    st.markdown("### 💱 Cotizaciones del Dólar")
    st.markdown("<p style='font-size: 12px; color: #78716c;'>Seguimiento de tipos de cambio oficiales, financieros y paralelos.</p>", unsafe_allow_html=True)
    st.markdown("---")
    render_dollar_cards(df_dolar)

elif "Pizarra" in seleccion_actual:
    st.markdown("### 🌾 Precios de Pizarra - Granos")
    st.markdown("<p style='font-size: 12px; color: #78716c;'>Cotizaciones oficiales de la Bolsa de Comercio de Rosario.</p>", unsafe_allow_html=True)
    st.markdown("---")
    if df_grains.empty:
        st.info("Todavía no hay datos de granos recolectados.")
    else:
        df_g = df_grains.copy()
        df_g.columns = ["Grano", "Mercado", "Precio (\$/TN)", "Precio (USD/TN)", "Variación (%)", "Actualización"]
        df_g["Precio ($/TN)"] = df_g["Precio ($/TN)"].apply(lambda x: f"\${x:,.2f}" if pd.notnull(x) else "-")
        df_g["Precio (USD/TN)"] = df_g["Precio (USD/TN)"].apply(lambda x: f"US\${x:,.2f}" if pd.notnull(x) else "-")
        df_g["Variación (%)"] = df_g["Variación (%)"].apply(lambda x: f"{x:+.2f}%" if pd.notnull(x) else "-")
        st.dataframe(df_g, hide_index=True, use_container_width=True)

elif "Combustibles" in seleccion_actual:
    st.markdown("### ⛽ Mercado Energético (Combustibles)")
    st.markdown("<p style='font-size: 12px; color: #78716c;'>Matriz comparativa de precios por bandera y localidad.</p>", unsafe_allow_html=True)
    st.markdown("---")
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
                pivot_fuel[col] = pivot_fuel[col].apply(lambda x: f
