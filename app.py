import json
import urllib.parse
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from streamlit_geolocation import streamlit_geolocation

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'fumigaciones.db'
CONFIG_PATH = BASE_DIR / 'data' / 'puntajes.json'
CONFIG_PATH.parent.mkdir(exist_ok=True)

QUESTIONS = [
    {
        'section': 'Detención de dengue y mosquitos',
        'id': 'dengue_1',
        'question': '¿HAZ OBSERVADO MOSQUITOS DENTRO O ALREDEDOR DE SU VIVIENDA?',
        'help': ''
    },
    {
        'section': 'Detención de dengue y mosquitos',
        'id': 'dengue_2',
        'question': '¿TIENES RECIPIENTES DONDE PUEDE ACUMULARSE AGUA?',
        'help': 'Ejemplo: CUBETAS, TAMBOS, LLANTAS, MACETAS, TINACOS, BEBEDEROS DE MASCOTAS, OTROS.'
    },
    {
        'section': 'Detención de dengue y mosquitos',
        'id': 'dengue_3',
        'question': '¿HAY AGUA ESTANCADA ACTUALMENTE',
        'help': ''
    },
    {
        'section': 'Detención de dengue y mosquitos',
        'id': 'dengue_4',
        'question': '¿HA HABIDO PERSONAS CON SINTOMAS COMPATIBLES CON DENGUE RECIENTEMENTE EN LA VIVIENDA?',
        'help': ''
    },
    {
        'section': 'Detención de dengue y mosquitos',
        'id': 'dengue_5',
        'question': '¿LA VIVIENDA HA SIDO FUMIGADA ANTERIORMENTE?',
        'help': ''
    },
    {
        'section': 'Medición de riesgo por garrapatas',
        'id': 'garrapata_1',
        'question': '¿TIENES PERRO O GATOS?',
        'help': ''
    },
    {
        'section': 'Medición de riesgo por garrapatas',
        'id': 'garrapata_2',
        'question': '¿HA OBSERVADO GARRAPATAS EN SUS MASCOTAS?',
        'help': ''
    },
    {
        'section': 'Medición de riesgo por garrapatas',
        'id': 'garrapata_3',
        'question': '¿HA OBSERVADO GARRAPATAS DENTRO DEL DOMICILIO?',
        'help': ''
    },
    {
        'section': 'Medición de riesgo por garrapatas',
        'id': 'garrapata_4',
        'question': '¿HA OBSERVADO GARRAPATAS EN PATIO, COCHERA O EXTERIORES?',
        'help': ''
    },
    {
        'section': 'Medición de riesgo por garrapatas',
        'id': 'garrapata_5',
        'question': '¿SUS MASCOTAS RECIBEN TRATAMIENTO PREVENTIVO CONTRA GARRAPATAS?',
        'help': ''
    },
    {
        'section': 'Medición de riesgo por garrapatas',
        'id': 'garrapata_6',
        'question': '¿EXISTE UN MENOR DE EDAD (12 AÑOS) O MAYOR DE EDAD (65 AÑOS)',
        'help': ''
    },
]

ENVIRONMENT = [
    'MALEZA ALTA', 'BASURA', 'LLANTAS ABANDONADAS', 'AGUA ESTANCADA', 'ESCOMBRO',
    'PATIO SIN LIMPIEZA', 'ANIMALES', 'TERRENOS BALDIOS CERCANOS',
    'DRENAJE CON PROBLEMAS', 'ACUMULACION DE OBJETOS'
]


def init_db():
    with sqlite3.connect(DB_PATH) as con:
        con.execute('''CREATE TABLE IF NOT EXISTS inspecciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            inspector TEXT,
            folio TEXT,
            domicilio TEXT,
            colonia TEXT,
            ubicacion TEXT,
            latitud REAL,
            longitud REAL,
            resultado TEXT,
            observaciones TEXT,
            respuestas_json TEXT NOT NULL,
            entorno_json TEXT NOT NULL,
            total_puntos REAL
        )''')
        con.commit()



def migrate_db():
    with sqlite3.connect(DB_PATH) as con:
        cols = {row[1] for row in con.execute("PRAGMA table_info(inspecciones)")}
        additions = {
            'ubicacion': 'TEXT',
            'latitud': 'REAL',
            'longitud': 'REAL',
            'resultado': 'TEXT'
        }
        for name, typ in additions.items():
            if name not in cols:
                con.execute(f'ALTER TABLE inspecciones ADD COLUMN {name} {typ}')
        con.commit()

def load_scores():
    if not CONFIG_PATH.exists():
        scores = {q['id']: {'SI': None, 'NO': None} for q in QUESTIONS}
        CONFIG_PATH.write_text(json.dumps(scores, ensure_ascii=False, indent=2), encoding='utf-8')
    return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))


def calculate_score(answers, scores):
    total = 0.0
    complete = True
    for qid, value in answers.items():
        pts = scores.get(qid, {}).get(value)
        if pts is None:
            complete = False
        else:
            total += float(pts)
    return total, complete


def save_record(data):
    with sqlite3.connect(DB_PATH) as con:
        con.execute('''INSERT INTO inspecciones
            (created_at, inspector, folio, domicilio, colonia, ubicacion, latitud, longitud,
             resultado, observaciones, respuestas_json, entorno_json, total_puntos)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (data['created_at'], data['inspector'], data['folio'], data['domicilio'],
             data['colonia'], data['ubicacion'], data['latitud'], data['longitud'],
             data['resultado'], data['observaciones'],
             json.dumps(data['respuestas'], ensure_ascii=False),
             json.dumps(data['entorno'], ensure_ascii=False),
             data['total_puntos']))
        con.commit()


init_db()
migrate_db()
scores = load_scores()

st.set_page_config(page_title='DISTRITO 12', page_icon='🦟', layout='wide')

st.markdown('''
<style>
.block-container { max-width: 1200px; padding-top: 1.2rem; }
.section-title { padding: 0.7rem 1rem; background:#0b2e63; color:white; border-radius:10px; font-size:1.15rem; font-weight:700; margin:1rem 0 0.7rem; }
.question { font-weight:650; font-size:1.02rem; }
.note { color:#5f6368; font-size:.9rem; }
.card { padding:1rem; border:1px solid #ddd; border-radius:12px; background:#fafafa; }
</style>
''', unsafe_allow_html=True)

st.title('🦟 DISTRITO 12')
st.caption('Encuesta de campo y seguimiento de viviendas del DISTRITO 12.')

with st.container(border=True):
    st.subheader('Datos de la visita')
    c1, c2 = st.columns(2)
    inspector = c1.text_input('Inspector / brigadista')
    folio = c2.text_input('Folio')

    domicilio = st.text_input('Domicilio')
    colonia = st.text_input('Colonia')

    st.markdown('### 📍 Ubicación del domicilio')

    ubicacion = st.text_input(
        'Referencia / ubicación',
        placeholder='Ej. Calle, colonia, referencia o punto de visita'
    )

    st.caption('Presiona el botón para tomar automáticamente la ubicación GPS del celular.')

    location = streamlit_geolocation()

    current_lat = 0.0
    current_lon = 0.0

    if location:
        lat_value = location.get('latitude')
        lon_value = location.get('longitude')

        if lat_value is not None and lon_value is not None:
            current_lat = float(lat_value)
            current_lon = float(lon_value)

    if current_lat != 0.0 and current_lon != 0.0:
        st.success('📍 Ubicación obtenida correctamente.')
        c_lat, c_lon = st.columns(2)
        c_lat.metric('Latitud', f'{current_lat:.6f}')
        c_lon.metric('Longitud', f'{current_lon:.6f}')

        mapa_url = (
            'https://www.google.com/maps/search/?api=1&query='
            f'{current_lat:.6f},{current_lon:.6f}'
        )

        # Mapa dentro de la aplicación con OpenStreetMap.
        # Esto evita que la capa de mapas de Streamlit aparezca en blanco.
        delta = 0.006
        left = current_lon - delta
        right = current_lon + delta
        bottom = current_lat - delta
        top = current_lat + delta

        osm_url = (
            'https://www.openstreetmap.org/export/embed.html?'
            + urllib.parse.urlencode({
                'bbox': f'{left},{bottom},{right},{top}',
                'layer': 'mapnik',
                'marker': f'{current_lat},{current_lon}'
            })
        )

        components.html(
            f'''
            <iframe
                src="{osm_url}"
                width="100%"
                height="420"
                style="border:1px solid #d0d0d0;border-radius:10px;"
                loading="lazy">
            </iframe>
            ''',
            height=440
        )

        st.link_button(
            '🗺️ ABRIR ESTA UBICACIÓN EN GOOGLE MAPS',
            mapa_url,
            use_container_width=True
        )

    else:
        st.info('📍 Presiona el botón de ubicación y permite el acceso al GPS cuando el navegador lo solicite.')

    latitud = current_lat if current_lat != 0.0 else None
    longitud = current_lon if current_lon != 0.0 else None

    resultado = st.selectbox(
        '🚪 Resultado de la visita',
        ['ABRIÓ', 'NO ABRIÓ', 'NO COINCIDE', 'OTRO']
    )

    observaciones = st.text_area('Observaciones generales', height=90)

answers = {}
for section in ['Detención de dengue y mosquitos', 'Medición de riesgo por garrapatas']:
    st.markdown(f'<div class="section-title">{section.upper()}</div>', unsafe_allow_html=True)
    qs = [q for q in QUESTIONS if q['section'] == section]
    for q in qs:
        st.markdown(f'<div class="question">{q["id"].split("_")[-1]}. {q["question"]}</div>', unsafe_allow_html=True)
        if q['help']:
            st.markdown(f'<div class="note">{q["help"]}</div>', unsafe_allow_html=True)
        answers[q['id']] = st.radio('Respuesta', ['SI', 'NO'], horizontal=True, key=q['id'], label_visibility='collapsed')

st.markdown('<div class="section-title">CONDICIONES DEL ENTORNO</div>', unsafe_allow_html=True)
st.write('REGISTRA SI EXISTE:')
environment = []
cols = st.columns(2)
for i, item in enumerate(ENVIRONMENT):
    if cols[i % 2].checkbox(item, key=f'env_{i}'):
        environment.append(item)


st.markdown('<div class="section-title">RESULTADO DE LA ENCUESTA</div>', unsafe_allow_html=True)
total, complete = calculate_score(answers, scores)
if complete:
    st.metric('Puntaje total', f'{total:g}')
else:
    st.info('El cálculo del puntaje queda pendiente de configurar los valores SI/NO definidos en la propuesta final.')

if st.button('💾 Guardar encuesta', type='primary', use_container_width=True):
    record = {
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'inspector': inspector,
        'folio': folio,
        'domicilio': domicilio,
        'colonia': colonia,
        'ubicacion': ubicacion,
        'latitud': latitud if latitud != 0 else None,
        'longitud': longitud if longitud != 0 else None,
        'resultado': resultado,
        'observaciones': observaciones,
        'respuestas': answers,
        'entorno': environment,
        'total_puntos': total if complete else None,
    }
    save_record(record)
    st.success('Encuesta guardada correctamente.')

with st.expander('📊 ESTADÍSTICAS DEL DISTRITO 12', expanded=True):
    with sqlite3.connect(DB_PATH) as con:
        stats_df = pd.read_sql_query(
            'SELECT resultado FROM inspecciones ORDER BY id DESC', con
        )

    total_encuestas = len(stats_df)
    abrieron = int((stats_df['resultado'] == 'ABRIÓ').sum()) if not stats_df.empty else 0
    no_abrieron = int((stats_df['resultado'] == 'NO ABRIÓ').sum()) if not stats_df.empty else 0
    no_coinciden = int((stats_df['resultado'] == 'NO COINCIDE').sum()) if not stats_df.empty else 0
    otros = int((stats_df['resultado'] == 'OTRO').sum()) if not stats_df.empty else 0

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric('Total encuestas', total_encuestas)
    m2.metric('🟢 Abrieron', abrieron)
    m3.metric('🔴 No abrieron', no_abrieron)
    m4.metric('🟠 No coinciden', no_coinciden)
    m5.metric('⚪ Otros', otros)

    if total_encuestas:
        chart = pd.DataFrame({
            'Resultado': ['ABRIÓ', 'NO ABRIÓ', 'NO COINCIDE', 'OTRO'],
            'Cantidad': [abrieron, no_abrieron, no_coinciden, otros]
        }).set_index('Resultado')
        st.bar_chart(chart)

with st.expander('📋 Registros guardados'):
    with sqlite3.connect(DB_PATH) as con:
        df = pd.read_sql_query(
            '''SELECT id, created_at, folio, inspector, domicilio, colonia,
                      ubicacion, latitud, longitud, resultado, total_puntos
               FROM inspecciones ORDER BY id DESC''',
            con
        )
    if df.empty:
        st.caption('Todavía no hay encuestas guardadas.')
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

with st.expander('⚙️ Configuración de puntajes'):
    st.write('El archivo de propuesta no trae los números del puntaje. Aquí se puede configurar posteriormente cada respuesta SI/NO sin cambiar el cuestionario.')
    edited = []
    for q in QUESTIONS:
        s = scores.get(q['id'], {})
        c1, c2, c3 = st.columns([5, 1, 1])
        c1.write(q['question'])
        si = c2.number_input('SI', value=float(s.get('SI') or 0), step=1.0, key=f'score_si_{q["id"]}')
        no = c3.number_input('NO', value=float(s.get('NO') or 0), step=1.0, key=f'score_no_{q["id"]}')
        edited.append((q['id'], si, no, s.get('SI') is None and s.get('NO') is None))
    if st.button('Guardar puntajes'):
        new_scores = {qid: {'SI': si, 'NO': no} for qid, si, no, _ in edited}
        CONFIG_PATH.write_text(json.dumps(new_scores, ensure_ascii=False, indent=2), encoding='utf-8')
        st.success('Puntajes guardados. Recarga la página para aplicarlos al formulario.')
