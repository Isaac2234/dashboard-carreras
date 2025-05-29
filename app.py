import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1) Configuración de la página y CSS ---
st.set_page_config(
    page_title="🏁 Dashboard 24H Le Mans",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.markdown(
    """
    <style>
      .css-1d391kg { background: #f0f2f6; }
      .stButton > button { background-color: #004080; color: white; }
      .stTabs [role=\"tab\"] { font-size: 16px; }
      [data-testid=\"stMetricValue\"] { color: #004080; }
    </style>
    """,
    unsafe_allow_html=True
)
st.title("🏎️ Análisis Interactivo 24 Hrs Le Mans")

# --- 2) Carga y preprocess de datos ---
@st.cache_data
def load_data(path):
    df = pd.read_csv(path, encoding='latin-1')
    df.drop(['S.No', 'Status'], axis=1, inplace=True)
    df.rename(columns=lambda c: c.strip().lstrip('# ').strip(), inplace=True)
    df['Car No.'] = df['Car No.'].astype(str)
    # Rellenar y codificar categóricas
    for col in ['Tyres', 'Category']:
        df[col] = df[col].fillna('Missing')
    df = pd.get_dummies(df, columns=['Tyres', 'Category'], dummy_na=False)
    # Velocidades
    df['Best Lap Kph'] = pd.to_numeric(df['Best Lap Kph'], errors='coerce')
    df['Best Lap Kph'] = df['Best Lap Kph'].fillna(df['Best Lap Kph'].median())
    # Total time y Hour
    tt = pd.to_datetime(df['Total Time'], format='%H:%M:%S', errors='coerce')
    df['total_time'] = (tt.dt.hour*3600 + tt.dt.minute*60 + tt.dt.second).astype(float)
    df['Hour'] = tt.dt.hour
    # Mejor vuelta en segundos
    blt = pd.to_datetime(df['Best LapTime'], format='%M:%S.%f', errors='coerce')
    df['Lap_record'] = (blt.dt.minute*60 + blt.dt.second + blt.dt.microsecond/1e6).astype(float)
    # Pitstops numéricos y eventos
    df['Pitstops'] = pd.to_numeric(df['Pitstops'], errors='coerce').fillna(0).astype(int)
    df['Pit_event'] = df.groupby('Car No.')['Pitstops'].diff().fillna(0).clip(lower=0).astype(int)
    return df

le_mans = load_data('24LeMans.csv')

# --- 3) Sidebar: filtros ---
with st.sidebar.expander('🔍 Filtros', expanded=True):
    equipos     = sorted(le_mans['Team'].unique())
    sel_equipos = st.multiselect('Equipos', equipos, default=equipos)
    pilotos     = sorted(le_mans['Drivers'].unique())
    sel_piloto  = st.selectbox('Piloto', ['Todos'] + pilotos)
    hmin, hmax  = int(le_mans['Hour'].min()), int(le_mans['Hour'].max())
    sel_hour    = st.slider('Hora (carrera)', hmin, hmax, (hmin, hmax))
    lmin, lmax  = int(le_mans['Laps'].min()), int(le_mans['Laps'].max())
    sel_laps    = st.slider('Vueltas', lmin, lmax, (lmin, lmax))
    show_raw    = st.checkbox('Mostrar tabla completa', value=False)

# --- 4) Aplicar filtros ---
mask = (
    le_mans['Team'].isin(sel_equipos) &
    le_mans['Hour'].between(sel_hour[0], sel_hour[1]) &
    le_mans['Laps'].between(sel_laps[0], sel_laps[1])
)
if sel_piloto != 'Todos':
    mask &= (le_mans['Drivers'] == sel_piloto)
filtered = le_mans.loc[mask].reset_index(drop=True)

# --- 5) Calcular pit-stops por hora ---
pit_per_hour = filtered.groupby('Hour')['Pit_event'].sum()

# --- 6) Layout con pestañas ---
tabs = st.tabs(['📍 Mapa', '📊 Resumen', '📈 Visualizaciones', '📋 Datos'])

# Mapa estático
with tabs[0]:
    st.header('📍 Circuit de la Sarthe')
    st.image('assets/lemans.png', use_container_width=True)

# Resumen métricas
with tabs[1]:
    st.header('🔑 Métricas Clave')
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Avg Total Time (s)', f"{filtered['total_time'].mean():.0f}")
    c2.metric('Avg Best Lap (s)',   f"{filtered['Lap_record'].mean():.2f}")
    c3.metric('Avg Pit-stops/events',f"{filtered['Pit_event'].mean():.1f}")
    c4.metric('Registros',           f"{len(filtered)}")

# Visualizaciones
with tabs[2]:
    st.header('📈 Visualizaciones')
    # Histograma de velocidades
    fig_v = px.histogram(
        filtered, x='Best Lap Kph', nbins=30, marginal='box',
        title='Distribución de Velocidades (Kph)'
    )
    st.plotly_chart(fig_v, use_container_width=True)
    # Total time por hora
    fig_t = px.line(
        filtered, x='Hour', y='total_time', color='Team', markers=True,
        title='Total Time Acumulado por Hora'
    )
    st.plotly_chart(fig_t, use_container_width=True)
    # Scatter mejor vuelta vs número
    dfp = filtered.dropna(subset=['Laps', 'Lap_record', 'Best Lap Kph'])
    fig_s = px.scatter(
        dfp, x='Laps', y='Lap_record', color='Team', size='Best Lap Kph',
        hover_data=['Car No.', 'Drivers'], title='Mejor Vuelta vs Nº Vuelta'
    )
    st.plotly_chart(fig_s, use_container_width=True)
    # Heatmap de media
    fig_h = px.density_heatmap(
        filtered, x='Hour', y='Team', z='Best Lap Kph', histfunc='avg',
        title='Velocidad Media por Hora y Equipo'
    )
    st.plotly_chart(fig_h, use_container_width=True)
    # Gráfico de pit-stops por hora
    pit_fig = px.bar(
        pit_per_hour.reset_index(), x='Hour', y='Pit_event',
        title='Eventos de Pit-stops por Hora',
        labels={'Pit_event': 'Número de Paradas'}
    )
    st.plotly_chart(pit_fig, use_container_width=True)

# Datos filtrados
with tabs[3]:
    st.header('🗄️ Resumen Agregado de Datos por Hora y Coche')
    # Agrupar por hora, coche y equipo
    agg_df = filtered.groupby(
        ['Hour','Car No.','Team','Drivers'], as_index=False
    ).agg(
        total_laps=('Laps','max'),
        avg_lap_record=('Lap_record','mean'),
        avg_speed=('Best Lap Kph','mean'),
        pit_events=('Pit_event','sum')
    )
    # Mostrar tabla agregada ordenada
    if show_raw:
        st.dataframe(
            agg_df.sort_values(['Hour','Car No.']),
            use_container_width=True
        )
    else:
        st.write('Marca **Mostrar tabla completa** para ver la tabla agregada.')

# Footer
st.markdown('---')

