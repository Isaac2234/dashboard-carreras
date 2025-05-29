import streamlit as st
import pandas as pd
import plotly.express as px

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
st.title("🏎 Análisis Interactivo 24 Hrs Le Mans")


@st.cache_data
def load_data(path):
    df = pd.read_csv(path, encoding='latin-1')
    df.drop(['S.No', 'Status'], axis=1, inplace=True)
    df.rename(columns=lambda c: c.strip().lstrip('# ').strip(), inplace=True)
    df['Car No.'] = df['Car No.'].astype(str)
    # Rellenar missing en Category y sólo dummyficar Tyres
    df['Category'] = df['Category'].fillna('Missing')
    df['Tyres']   = df['Tyres'].fillna('Missing')
    df = pd.get_dummies(df, columns=['Tyres'], dummy_na=False)
    df['Best Lap Kph'] = pd.to_numeric(df['Best Lap Kph'], errors='coerce')
    df['Best Lap Kph'] = df['Best Lap Kph'].fillna(df['Best Lap Kph'].median())
    tt = pd.to_datetime(df['Total Time'], format='%H:%M:%S', errors='coerce')
    df['total_time'] = (tt.dt.hour * 3600 + tt.dt.minute * 60 + tt.dt.second).astype(float)
    df['Hour'] = tt.dt.hour
    blt = pd.to_datetime(df['Best LapTime'], format='%M:%S.%f', errors='coerce')
    df['Lap_record'] = (blt.dt.minute * 60 + blt.dt.second + blt.dt.microsecond / 1e6).astype(float)
    df['Pitstops'] = pd.to_numeric(df['Pitstops'], errors='coerce').fillna(0).astype(int)
    df['Pitstop_Binary'] = (df['Pitstops'] > 0).astype(int)
    df['Laps'] = pd.to_numeric(df['Laps'], errors='coerce').fillna(0).astype(int)
    return df

le_mans = load_data('24LeMans.csv')


with st.sidebar.expander('🔍 Filtros', expanded=True):
    equipos     = sorted(le_mans['Team'].unique())
    sel_equipos = st.multiselect('Equipos', equipos, default=equipos)
    pilotos     = sorted(le_mans['Drivers'].unique())
    sel_piloto  = st.selectbox('Piloto', ['Todos'] + pilotos)
    # Filtro de Category
    categorias      = sorted(le_mans['Category'].unique())
    sel_categorias  = st.multiselect('Categorías', categorias, default=categorias)
    hmin, hmax  = int(le_mans['Hour'].min()), int(le_mans['Hour'].max())
    sel_hour    = st.slider('Hora (carrera)', hmin, hmax, (hmin, hmax))
    lmin, lmax  = int(le_mans['Laps'].min()), int(le_mans['Laps'].max())
    sel_laps    = st.slider('Vueltas', lmin, lmax, (lmin, lmax))
    show_raw    = st.checkbox('Mostrar tabla completa', value=False)


# Máscara de filtrado incluyendo Category
mask = (
    le_mans['Team'].isin(sel_equipos) &
    le_mans['Category'].isin(sel_categorias) &
    le_mans['Hour'].between(sel_hour[0], sel_hour[1]) &
    le_mans['Laps'].between(sel_laps[0], sel_laps[1])
)
if sel_piloto != 'Todos':
    mask &= (le_mans['Drivers'] == sel_piloto)
filtered = le_mans.loc[mask].reset_index(drop=True)

tabs = st.tabs(['📍 Mapa', '📊 Resumen', '📈 Visualizaciones', '📋 Datos'])

with tabs[0]:
    st.header('📍 Circuit de la Sarthe')
    st.image('assets/lemans.png', use_container_width=True)

with tabs[1]:
    st.header('🔑 Métricas Clave')
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Avg Total Time (s)', f"{filtered['total_time'].mean():.0f}")
    c2.metric('Avg Best Lap (s)',   f"{filtered['Lap_record'].mean():.2f}")
    c3.metric('Avg Pit-stops',       f"{filtered['Pitstops'].mean():.1f}")
    c4.metric('Registros',           f"{len(filtered)}")

with tabs[2]:
    st.header('📈 Visualizaciones')
    fig_v = px.histogram(
        filtered, x='Best Lap Kph', nbins=30, marginal='box',
        title='Distribución de Velocidades (Kph)'
    )
    st.plotly_chart(fig_v, use_container_width=True)

    fig_t = px.line(
        filtered, x='Hour', y='total_time', color='Team', markers=True,
        title='Total Time Acumulado por Hora'
    )
    st.plotly_chart(fig_t, use_container_width=True)

    dfp = filtered.dropna(subset=['Laps', 'Lap_record', 'Best Lap Kph'])
    fig_s = px.scatter(
        dfp, x='Laps', y='Lap_record', color='Team', size='Best Lap Kph',
        hover_data=['Car No.', 'Drivers'], title='Mejor Vuelta vs Nº Vuelta'
    )
    st.plotly_chart(fig_s, use_container_width=True)

    fig_h = px.density_heatmap(
        filtered, x='Hour', y='Team', z='Best Lap Kph', histfunc='avg',
        title='Velocidad Media por Hora y Equipo'
    )
    st.plotly_chart(fig_h, use_container_width=True)

    pit_hour_team = (
        filtered
        .groupby(['Hour','Team'], as_index=False)
        .agg(Pitstop_Occurred=('Pitstop_Binary','max'))
    )
    fig_pits = px.bar(
        pit_hour_team,
        x='Hour',
        y='Pitstop_Occurred',
        color='Team',
        barmode='group',
        title='Presencia de Pit-stops por Hora y Equipo',
        labels={'Pitstop_Occurred': '¿Hubo parada? (0/1)', 'Hour': 'Hora de Carrera'}
    )
    fig_pits.update_yaxes(tickvals=[0, 1])
    st.plotly_chart(fig_pits, use_container_width=True)

with tabs[3]:
    st.header('🗄 Resumen Agregado de Datos por Hora y Coche')
    agg_df = filtered.groupby(
        ['Hour','Car No.','Team','Drivers'], as_index=False
    ).agg(
        total_laps=('Laps','max'),
        avg_lap_record=('Lap_record','mean'),
        avg_speed=('Best Lap Kph','mean'),
    )
    if show_raw:
        st.dataframe(
            agg_df.sort_values(['Hour','Car No.']),
            use_container_width=True
        )
    else:
        st.write('Marca *Mostrar tabla completa* para ver la tabla agregada.')

st.markdown('---')