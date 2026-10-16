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
    /* Tipografía y fondo general estilo granos.ar */
    .main {
        background-color: #faf9f6;
    }
    
    /* Estilo de la barra lateral */
    section[data-testid="stSidebar"] {
        background-color: #f5f3ef;
        border-right: 1px solid #e7e2d9;
    }
    
    /* Grilla de tarjetas adaptable a celulares */
    .market-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
        gap: 12px;
        margin-top: 10px;
        margin-bottom: 25px;
    }
    
    @media (max-width: 640px) {
        .market-grid {
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
        }
    }

    /* Tarjetas estilo granos.ar / terminal */
    .market-card {
        background-color: #ffffff;
        border: 1px solid #e5e0d8;
        border-radius: 8px;
        padding: 12px 14px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02);
        transition: transform 0.1s ease;
    }
    
    .card-blue { border-top: 3px solid #3b82f6; }
    .card-green { border-top: 3px solid #10b981; }
    .card-purple { border-top: 3px solid #8b5cf6; }
    .card-indigo { border-top: 3px solid #6366f1; }
    .card-amber { border-top: 3px solid #d97706; }
    .card-emerald { border-top: 3px solid #059669; }
    .card-yellow { border-top: 3px solid #eab308; }
    .card-gray { border-top: 3px solid #78716c; }

    .card-title {
        font-size: 10px;
        font-weight: 700;
        color: #78716c;
        letter-spacing: 0.4px;
        margin-bottom: 4px;
        text-transform: uppercase;
    }
    .card-price-main {
        font-size: 20px;
        font-weight: 700;
        color: #1c1917;
        margin-bottom: 2px;
    }
    .card-subtext {
        font-size: 11px;
        color: #8c857b;
    }
    .badge-pos {
        color: #10b981;
        font-weight: 600;
        font-size: 11px;
    }
    .badge-neg {
        color: #ef4444;
        font-weight: 600;
        font-size: 11px;
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
# FUNCIONES RENDERIZADORAS DE TARJETAS
# ==========================================
def render_dollar_cards(df):
    if df.empty:
        st.info("Sin registros de dólares.")
        return

    cards_html = '<div class="market-grid">'
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
        cards_html += f'<div class="market-card {accent}"><div class="card-title">{nombre}</div><div class="card-price-main">{str_venta}</div><div class="card-subtext">C: {str_compra} / V: {str_venta}</div></div>'
        
    cards_html += '</div>'
    st.markdown(cards_html, unsafe_allow_html=True)

def render_grain_cards(df):
    if df.empty:
        st.info("Sin registros de granos.")
        return

    cards_html = '<div class="market-grid">'
    def get_grain_accent(name):
        n = str(name).lower()
        if 'soja' in n: return 'card-emerald'
        if 'maiz' in n or 'maíz' in n: return 'card-yellow'
        if 'trigo' in n: return 'card-amber'
        if 'girasol' in n: return 'card-purple'
        return 'card-gray'

    for _, row in df.iterrows():
        grano = row.get('grain_name', 'Cultivo')
        ars = row.get('price_ars')
        usd = row.get('price_usd')
        var = row.get('variation', 0)
        
        str_ars = f"\${ars:,.0f}".replace(",", ".") if pd.notnull(ars) else "-"
        str_usd = f"US\${usd:,.2f}" if pd.notnull(usd) else "-"
        
        var_html = ""
        if pd.notnull(var) and var != 0:
            badge_cls = "badge-pos" if var > 0 else "badge-neg"
            var_html = f'<span class="{badge_cls}">{var:+.2f}%</span>'

        accent = get_grain_accent(grano)
        cards_html += f'<div class="market-card {accent}"><div class="card-title">{grano} {var_html}</div><div class="card-price-main">{str_ars}</div><div class="card-subtext">{str_usd} / TN</div></div>'
        
    cards_html += '</div>'
    st.markdown(cards_html, unsafe_allow_html=True)

def render_fuel_cards(df, selected_city):
    if df.empty:
        st.info("Sin registros de combustibles.")
        return
        
    df_c = df[df["city"].str.upper().str.strip() == selected_city.upper().strip()].copy()
    if df_c.empty:
        st.info(f"Sin registros para {selected_city}.")
        return

    df_c["fuel_category"] = df_c["fuel_type"].apply(normalize_fuel)
    cards_html = '<div class="market-grid">'
    
    def get_fuel_accent(fuel):
        f = str(fuel).lower()
        if 'súper' in f or 'super' in f: return 'card-green'
        if 'premium' in f: return 'card-blue'
        if 'gasoil' in f or 'diesel' in f: return 'card-amber'
        if 'gnc' in f: return 'card-indigo'
        return 'card-gray'

    fuel_grouped = df_c.groupby("fuel_category")["price"].mean().reset_index()

    for _, row in fuel_grouped.iterrows():
        comb = row['fuel_category']
        precio = row['price']
        str_precio = f"\${precio:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notnull(precio) else "-"
        accent = get_fuel_accent(comb)
        cards_html += f'<div class="market-card {accent}"><div class="card-title">{comb}</div><div class="card-price-main">{str_precio}</div><div class="card-subtext">Promedio {selected_city}</div></div>'
        
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
    
    st.markdown("##### 🌾 Pizarra de Granos (Referencia BCR / Disponible)")
    render_grain_cards(df_grains)

elif "Dólares" in seleccion_actual:
