import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "fumigaciones.db"
CONFIG_PATH = BASE_DIR / "data" / "puntajes.json"
CONFIG_PATH.parent.mkdir(exist_ok=True)

QUESTIONS = [
    {"section": "Detención de dengue y mosquitos", "id": "dengue_1",
     "question": "¿HAZ OBSERVADO MOSQUITOS DENTRO O ALREDEDOR DE SU VIVIENDA?", "help": ""},
    {"section": "Detención de dengue y mosquitos", "id": "dengue_2",
     "question": "¿TIENES RECIPIENTES DONDE PUEDE ACUMULARSE AGUA?",
     "help": "Ejemplo: CUBETAS, TAMBOS, LLANTAS, MACETAS, TINACOS, BEBEDEROS DE MASCOTAS, OTROS."},
    {"section": "Detención de dengue y mosquitos", "id": "dengue_3",
     "question": "¿HAY AGUA ESTANCADA ACTUALMENTE", "help": ""},
    {"section": "Detención de dengue y mosquitos", "id": "dengue_4",
     "question": "¿HA HABIDO PERSONAS CON SINTOMAS COMPATIBLES CON DENGUE RECIENTEMENTE EN LA VIVIENDA?", "help": ""},
    {"section": "Detención de dengue y mosquitos", "id": "dengue_5",
     "question": "¿LA VIVIENDA HA SIDO FUMIGADA ANTERIORMENTE?", "help": ""},
    {"section": "Medición de riesgo por garrapatas", "id": "garrapata_1",
     "question": "¿TIENES PERRO O GATOS?", "help": ""},
    {"section": "Medición de riesgo por garrapatas", "id": "garrapata_2",
     "question": "¿HA OBSERVADO GARRAPATAS EN SUS MASCOTAS?", "help": ""},
    {"section": "Medición de riesgo por garrapatas", "id": "garrapata_3",
     "question": "¿HA OBSERVADO GARRAPATAS DENTRO DEL DOMICILIO?", "help": ""},
    {"section": "Medición de riesgo por garrapatas", "id": "garrapata_4",
     "question": "¿HA OBSERVADO GARRAPATAS EN PATIO, COCHERA O EXTERIORES?", "help": ""},
    {"section": "Medición de riesgo por garrapatas", "id": "garrapata_5",
     "question": "¿SUS MASCOTAS RECIBEN TRATAMIENTO PREVENTIVO CONTRA GARRAPATAS?", "help": ""},
    {"section": "Medición de riesgo por garrapatas", "id": "garrapata_6",
     "question": "¿EXISTE UN MENOR DE EDAD (12 AÑOS) O MAYOR DE EDAD (65 AÑOS)", "help": ""},
]

ENVIRONMENT = [
    "MALEZA ALTA", "BASURA", "LLANTAS ABANDONADAS", "AGUA ESTANCADA", "ESCOMBRO",
    "PATIO SIN LIMPIEZA", "ANIMALES", "TERRENOS BALDIOS CERCANOS",
    "DRENAJE CON PROBLEMAS", "ACUMULACION DE OBJETOS"
]

def init_db():
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS inspecciones (
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
        )""")
        con.commit()

def migrate_db():
    with sqlite3.connect(DB_PATH) as con:
        cols = {row[1] for row in con.execute("PRAGMA table_info(inspecciones)")}
        additions = {
            "ubicacion": "TEXT", "latitud": "REAL", "longitud": "REAL", "resultado": "TEXT"
        }
        for name, typ in additions.items():
            if name not in cols:
                con.execute(f"ALTER TABLE inspecciones ADD COLUMN {name} {typ}")
        con.commit()

def load_scores():
    if not CONFIG_PATH.exists():
        scores = {q["id"]: {"SI": None, "NO": None} for q in QUESTIONS}
        CONFIG_PATH.write_text(json.dumps(scores, ensure_ascii=False, indent=2), encoding="utf-8")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

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
        con.execute("""INSERT INTO inspecciones
            (created_at, inspector, folio, domicilio, colonia, ubicacion, latitud, longitud,
             resultado, observaciones, respuestas_json, entorno_json, total_puntos)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["created_at"], data["inspector"], data["folio"], data["domicilio"],
             data["colonia"], data["ubicacion"], data["latitud"], data["longitud"],
             data["resultado"], data["observaciones"],
             json.dumps(data["respuestas"], ensure_ascii=False),
             json.dumps(data["entorno"], ensure_ascii=False), data["total_puntos"]))
        con.commit()

def aplicar_gps_desde_url():
    try:
        qp = st.query_params
        gps_lat = qp.get("gps_lat")
        gps_lon = qp.get("gps_lon")
        if isinstance(gps_lat, list):
            gps_lat = gps_lat[0]
        if isinstance(gps_lon, list):
            gps_lon = gps_lon[0]
        if gps_lat and gps_lon:
            st.session_state.lat_manual_d12 = float(gps_lat)
            st.session_state.lon_manual_d12 = float(gps_lon)
            st.session_state.msg_geo_d12 = "Ubicación GPS tomada desde el celular"
            try:
                st.query_params.clear()
            except Exception:
                pass
    except Exception:
        pass

def boton_gps_celular():
    components.html("""
    <div style="font-family:Arial,sans-serif;width:100%;">
      <button id="gpsBtn" style="
        width:100%;padding:13px 14px;border:0;border-radius:10px;
        background:#0b2e63;color:white;font-weight:800;font-size:16px;cursor:pointer;">
        📍 OBTENER UBICACIÓN ACTUAL
      </button>
      <div id="gpsMsg" style="margin-top:8px;font-size:13px;color:#475569;font-weight:700;"></div>
      <script>
        const btn = document.getElementById("gpsBtn");
        const msg = document.getElementById("gpsMsg");
        btn.onclick = function() {
          if (!navigator.geolocation) {
            msg.innerHTML = "Tu navegador no permite geolocalización.";
            return;
          }
          msg.innerHTML = "📍 Solicitando permiso de ubicación...";
          navigator.geolocation.getCurrentPosition(
            function(pos) {
              const lat = pos.coords.latitude.toFixed(8);
              const lon = pos.coords.longitude.toFixed(8);
              msg.innerHTML = "✅ Ubicación tomada: " + lat + ", " + lon;
              const url = new URL(window.parent.location.href);
              url.searchParams.set("gps_lat", lat);
              url.searchParams.set("gps_lon", lon);
              window.parent.location.href = url.toString();
            },
            function(err) {
              let texto = "No se pudo obtener la ubicación.";
              if (err.code === 1) texto = "❌ Permiso denegado. Activa la ubicación del navegador.";
              if (err.code === 2) texto = "❌ Ubicación no disponible. Revisa GPS o señal.";
              if (err.code === 3) texto = "❌ La solicitud tardó demasiado. Intenta de nuevo.";
              msg.innerHTML = texto;
            },
            {enableHighAccuracy:true, timeout:15000, maximumAge:0}
          );
        };
      </script>
    </div>
    """, height=95)

init_db()
migrate_db()
aplicar_gps_desde_url()
scores = load_scores()

st.set_page_config(page_title="DISTRITO 12", page_icon="🦟", layout="wide")

st.markdown("""
<style>
.block-container { max-width: 1200px; padding-top: 1.2rem; }
.section-title { padding: .7rem 1rem; background:#0b2e63; color:white;
border-radius:10px; font-size:1.15rem; font-weight:700; margin:1rem 0 .7rem; }
.question { font-weight:650; font-size:1.02rem; }
.note { color:#5f6368; font-size:.9rem; }
</style>
""", unsafe_allow_html=True)

st.title("🦟 DISTRITO 12")
st.caption("Encuesta de campo y seguimiento de viviendas del DISTRITO 12.")

with st.container(border=True):
    st.subheader("Datos de la visita")
    c1, c2 = st.columns(2)
    inspector = c1.text_input("Inspector / brigadista")
    folio = c2.text_input("Folio")
    domicilio = st.text_input("Domicilio")
    colonia = st.text_input("Colonia")

    st.markdown("### 📍 Ubicación del domicilio")
    ubicacion = st.text_input(
        "Referencia / ubicación",
        placeholder="Ej. Calle, colonia, referencia o punto de visita"
    )
    st.caption("En el celular, presiona el botón y permite el acceso a la ubicación.")
    boton_gps_celular()

    current_lat = st.session_state.get("lat_manual_d12")
    current_lon = st.session_state.get("lon_manual_d12")

    if current_lat is not None and current_lon is not None:
        st.success("📍 Ubicación obtenida correctamente.")

        c_lat, c_lon = st.columns(2)
        c_lat.metric("Latitud", f"{current_lat:.6f}")
        c_lon.metric("Longitud", f"{current_lon:.6f}")

        # SEGUNDO BOTÓN: abre exactamente la ubicación capturada en Google Maps.
        mapa_url = (
            "https://www.google.com/maps/search/?api=1&query="
            f"{current_lat:.6f},{current_lon:.6f}"
        )
        st.link_button(
            "🗺️ ABRIR MAPA",
            mapa_url,
            use_container_width=True
        )

        st.caption("La ubicación se guardará con la encuesta al presionar «Guardar encuesta».")
    else:
        st.info("📍 Presiona «OBTENER UBICACIÓN ACTUAL» y permite el acceso al GPS.")

    latitud = current_lat
    longitud = current_lon

    resultado = st.selectbox(
        "🚪 Resultado de la visita",
        ["ABRIÓ", "NO ABRIÓ", "NO COINCIDE", "OTRO"]
    )
    observaciones = st.text_area("Observaciones generales", height=90)

answers = {}
for section in ["Detención de dengue y mosquitos", "Medición de riesgo por garrapatas"]:
    st.markdown(f'<div class="section-title">{section.upper()}</div>', unsafe_allow_html=True)
    qs = [q for q in QUESTIONS if q["section"] == section]
    for q in qs:
        st.markdown(
            f'<div class="question">{q["id"].split("_")[-1]}. {q["question"]}</div>',
            unsafe_allow_html=True
        )
        if q["help"]:
            st.markdown(f'<div class="note">{q["help"]}</div>', unsafe_allow_html=True)
        answers[q["id"]] = st.radio(
            "Respuesta", ["SI", "NO"], horizontal=True,
            key=q["id"], label_visibility="collapsed"
        )

st.markdown('<div class="section-title">CONDICIONES DEL ENTORNO</div>', unsafe_allow_html=True)
st.write("REGISTRA SI EXISTE:")
environment = []
cols = st.columns(2)
for i, item in enumerate(ENVIRONMENT):
    if cols[i % 2].checkbox(item, key=f"env_{i}"):
        environment.append(item)

st.markdown('<div class="section-title">RESULTADO DE LA ENCUESTA</div>', unsafe_allow_html=True)
total, complete = calculate_score(answers, scores)
if complete:
    st.metric("Puntaje total", f"{total:g}")
else:
    st.info("El cálculo del puntaje queda pendiente de configurar los valores SI/NO.")

if st.button("💾 Guardar encuesta", type="primary", use_container_width=True):
    record = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "inspector": inspector, "folio": folio, "domicilio": domicilio,
        "colonia": colonia, "ubicacion": ubicacion,
        "latitud": latitud, "longitud": longitud,
        "resultado": resultado, "observaciones": observaciones,
        "respuestas": answers, "entorno": environment,
        "total_puntos": total if complete else None,
    }
    save_record(record)
    st.success("Encuesta guardada correctamente.")

with st.expander("📊 ESTADÍSTICAS DEL DISTRITO 12", expanded=True):
    with sqlite3.connect(DB_PATH) as con:
        stats_df = pd.read_sql_query(
            "SELECT resultado FROM inspecciones ORDER BY id DESC", con
        )

    total_encuestas = len(stats_df)
    abrieron = int((stats_df["resultado"] == "ABRIÓ").sum()) if not stats_df.empty else 0
    no_abrieron = int((stats_df["resultado"] == "NO ABRIÓ").sum()) if not stats_df.empty else 0
    no_coinciden = int((stats_df["resultado"] == "NO COINCIDE").sum()) if not stats_df.empty else 0
    otros = int((stats_df["resultado"] == "OTRO").sum()) if not stats_df.empty else 0

    m1,m2,m3,m4,m5 = st.columns(5)
    m1.metric("Total encuestas", total_encuestas)
    m2.metric("🟢 Abrieron", abrieron)
    m3.metric("🔴 No abrieron", no_abrieron)
    m4.metric("🟠 No coinciden", no_coinciden)
    m5.metric("⚪ Otros", otros)

    if total_encuestas:
        chart = pd.DataFrame({
            "Resultado": ["ABRIÓ","NO ABRIÓ","NO COINCIDE","OTRO"],
            "Cantidad": [abrieron,no_abrieron,no_coinciden,otros]
        }).set_index("Resultado")
        st.bar_chart(chart)

with st.expander("🗺️ MAPA DE UBICACIONES GUARDADAS", expanded=True):
    with sqlite3.connect(DB_PATH) as con:
        mapa_guardado = pd.read_sql_query(
            """SELECT id, created_at, folio, inspector, domicilio, colonia,
                      resultado, latitud, longitud
               FROM inspecciones
               WHERE latitud IS NOT NULL AND longitud IS NOT NULL
                     AND latitud != 0 AND longitud != 0
               ORDER BY id DESC""", con)

    if mapa_guardado.empty:
        st.info("Todavía no hay ubicaciones guardadas. Captura una encuesta y guarda el registro.")
    else:
        mapa_df = mapa_guardado[["latitud", "longitud"]].copy()
        mapa_df["latitud"] = pd.to_numeric(mapa_df["latitud"], errors="coerce")
        mapa_df["longitud"] = pd.to_numeric(mapa_df["longitud"], errors="coerce")
        mapa_df = mapa_df.dropna()

        if not mapa_df.empty:
            st.map(mapa_df, latitude="latitud", longitude="longitud", zoom=12, use_container_width=True)
            st.caption(f"📍 {len(mapa_df)} ubicaciones guardadas en el DISTRITO 12.")

with st.expander("📋 Registros guardados"):
    with sqlite3.connect(DB_PATH) as con:
        df = pd.read_sql_query(
            """SELECT id, created_at, folio, inspector, domicilio, colonia,
                      ubicacion, latitud, longitud, resultado, total_puntos
               FROM inspecciones ORDER BY id DESC""", con)
    if df.empty:
        st.caption("Todavía no hay encuestas guardadas.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

with st.expander("⚙️ Configuración de puntajes"):
    st.write("Configura posteriormente los valores SI/NO de cada pregunta.")
    edited = []
    for q in QUESTIONS:
        s = scores.get(q["id"], {})
        c1,c2,c3 = st.columns([5,1,1])
        c1.write(q["question"])
        si = c2.number_input("SI", value=float(s.get("SI") or 0), step=1.0,
                             key=f"score_si_{q['id']}")
        no = c3.number_input("NO", value=float(s.get("NO") or 0), step=1.0,
                             key=f"score_no_{q['id']}")
        edited.append((q["id"],si,no))
    if st.button("Guardar puntajes"):
        new_scores = {qid: {"SI":si,"NO":no} for qid,si,no in edited}
        CONFIG_PATH.write_text(
            json.dumps(new_scores, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        st.success("Puntajes guardados. Recarga la página.")
