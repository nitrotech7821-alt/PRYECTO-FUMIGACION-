import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import html

# IMPORTANTE: Streamlit exige que set_page_config sea la primera llamada de Streamlit.
st.set_page_config(page_title="DISTRITO 12", page_icon="🦟", layout="wide")

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
            # No borrar los parámetros GPS aquí.
            # Se conservan para que el estado de Streamlit no se pierda
            # y el botón ABRIR MAPA pueda usar las coordenadas capturadas.
    except Exception:
        pass

def componentes_ubicacion():
    """Botones GPS y mapa. La ubicación se conserva en el navegador y se sincroniza
    con Streamlit cuando el usuario pulsa ABRIR MAPA."""
    current_lat = st.session_state.get("lat_manual_d12")
    current_lon = st.session_state.get("lon_manual_d12")

    gps_lat = "" if current_lat is None else f"{float(current_lat):.8f}"
    gps_lon = "" if current_lon is None else f"{float(current_lon):.8f}"

    components.html(f"""
    <div style="font-family:Arial,sans-serif;width:100%;box-sizing:border-box;">
      <button id="gpsBtn" style="
        width:100%;height:58px;padding:10px 16px;border:0;border-radius:10px;
        background:#303030;color:#fff;font-weight:800;font-size:18px;cursor:pointer;
        box-shadow:0 3px 7px rgba(0,0,0,.18);">
        OBTENER UBICACIÓN &nbsp;📍
      </button>

      <div id="gpsMsg" style="
        margin-top:9px;min-height:18px;font-size:14px;color:#666;text-align:center;">
      </div>

      <a id="mapBtn" href="#" target="_blank" rel="noopener noreferrer"
         style="
           display:flex;align-items:center;justify-content:center;
           width:100%;height:58px;padding:0 16px;box-sizing:border-box;
           border:0;border-radius:10px;
           background:#eeeeee;color:#aaaaaa;text-decoration:none;
           font-weight:800;font-size:18px;cursor:not-allowed;
           box-shadow:0 3px 7px rgba(0,0,0,.18);margin-top:10px;">
        ABRIR MAPA &nbsp;🗺️
      </a>

      <script>
        const btn = document.getElementById('gpsBtn');
        const mapBtn = document.getElementById('mapBtn');
        const msg = document.getElementById('gpsMsg');

        let lat = {gps_lat!r};
        let lon = {gps_lon!r};

        function activarMapa(la, lo) {{
          lat = String(la);
          lon = String(lo);

          mapBtn.href = 'https://www.google.com/maps?q=' +
                        encodeURIComponent(lat + ',' + lon);
          mapBtn.style.background = '#303030';
          mapBtn.style.color = '#fff';
          mapBtn.style.cursor = 'pointer';
        }}

        // Si el GPS ya fue obtenido antes, recuperarlo del navegador.
        try {{
          const guardada = JSON.parse(localStorage.getItem('d12_gps_ubicacion') || 'null');
          if ((!lat || !lon) && guardada && guardada.lat && guardada.lon) {{
            activarMapa(guardada.lat, guardada.lon);
          }} else if (lat && lon) {{
            activarMapa(lat, lon);
          }}
        }} catch (e) {{
          if (lat && lon) activarMapa(lat, lon);
        }}

        btn.onclick = function() {{
          if (!navigator.geolocation) {{
            msg.innerHTML = '❌ Este navegador no permite obtener la ubicación.';
            return;
          }}

          msg.innerHTML = '📍 Obteniendo ubicación GPS...';

          navigator.geolocation.getCurrentPosition(
            function(pos) {{
              const la = pos.coords.latitude.toFixed(8);
              const lo = pos.coords.longitude.toFixed(8);

              activarMapa(la, lo);
              msg.innerHTML = '✅ Ubicación obtenida correctamente.';

              // Guardar inmediatamente en el navegador.
              localStorage.setItem(
                'd12_gps_ubicacion',
                JSON.stringify({{lat: la, lon: lo}})
              );
            }},
            function(err) {{
              let t = '❌ No se pudo obtener la ubicación.';
              if (err.code === 1)
                t = '❌ Permiso denegado. Permite la ubicación en el celular.';
              if (err.code === 2)
                t = '❌ Ubicación no disponible. Revisa el GPS.';
              if (err.code === 3)
                t = '❌ Se agotó el tiempo. Intenta nuevamente.';
              msg.innerHTML = t;
            }},
            {{enableHighAccuracy:true, timeout:20000, maximumAge:0}}
          );
        }};

        // El mismo clic abre Google Maps Y sincroniza las coordenadas
        // con la página principal de Streamlit para poder guardarlas.
        mapBtn.onclick = function(e) {{
          if (!lat || !lon) {{
            e.preventDefault();
            msg.innerHTML = '⚠️ Primero presiona OBTENER UBICACIÓN.';
            return;
          }}

          try {{
            const url = new URL(window.parent.location.href);
            url.searchParams.set('gps_lat', lat);
            url.searchParams.set('gps_lon', lon);

            // Este cambio se ejecuta por el clic del usuario, por lo que
            // el navegador permite navegar la página principal.
            window.parent.location.href = url.toString();
          }} catch (err) {{
            // Google Maps sigue abriéndose aunque el navegador no permita
            // modificar la ventana principal desde el componente.
          }}
        }};
      </script>
    </div>
    """, height=155)


def mapa_ubicaciones_guardadas(df):
    """Mapa Leaflet con todos los puntos guardados y su información."""
    if df.empty:
        st.info("Todavía no hay ubicaciones guardadas. Captura una encuesta y guarda el registro.")
        return

    # Preparar registros seguros para JavaScript.
    puntos = []
    for _, r in df.iterrows():
        try:
            lat = float(r["latitud"])
            lon = float(r["longitud"])
        except Exception:
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        resultado = str(r.get("resultado") or "SIN RESULTADO")
        colores = {
            "ABRIÓ": "#16a34a",
            "NO ABRIÓ": "#dc2626",
            "NO COINCIDE": "#f59e0b",
            "OTRO": "#64748b",
        }
        color = colores.get(resultado, "#2563eb")
        popup = (
            f"<b>Encuesta #{html.escape(str(r.get('id','')))}</b><br>"
            f"<b>Resultado:</b> {html.escape(resultado)}<br>"
            f"<b>Folio:</b> {html.escape(str(r.get('folio') or ''))}<br>"
            f"<b>Inspector:</b> {html.escape(str(r.get('inspector') or ''))}<br>"
            f"<b>Domicilio:</b> {html.escape(str(r.get('domicilio') or ''))}<br>"
            f"<b>Colonia:</b> {html.escape(str(r.get('colonia') or ''))}<br>"
            f"<b>Ubicación:</b> {html.escape(str(r.get('ubicacion') or ''))}<br>"
            f"<b>Fecha:</b> {html.escape(str(r.get('created_at') or ''))}<br>"
            f"<b>GPS:</b> {lat:.6f}, {lon:.6f}"
        )
        label = str(r.get("folio") or r.get("domicilio") or f"#{r.get('id','')}")
        puntos.append({"lat": lat, "lon": lon, "color": color, "popup": popup, "label": label})

    import json as _json
    puntos_js = _json.dumps(puntos, ensure_ascii=False).replace("</", "<\\/")
    # Centro: promedio de los puntos para que el mapa quede sobre el distrito visitado.
    center_lat = sum(x["lat"] for x in puntos) / len(puntos)
    center_lon = sum(x["lon"] for x in puntos) / len(puntos)

    components.html(f"""
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <div id="mapaDistrito12" style="width:100%;height:620px;border:1px solid #ddd;border-radius:12px;overflow:hidden;"></div>
    <script>
      const puntosD12 = {puntos_js};
      const mapa = L.map('mapaDistrito12', {{zoomControl:true}}).setView([{center_lat:.6f}, {center_lon:.6f}], 13);
      L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors'
      }}).addTo(mapa);

      const bounds = [];
      puntosD12.forEach(p => {{
        const marker = L.circleMarker([p.lat, p.lon], {{
          radius: 9, color:'#ffffff', weight:2, fillColor:p.color, fillOpacity:0.95
        }}).addTo(mapa);
        marker.bindPopup(p.popup);
        marker.bindTooltip(p.label, {{permanent:false, direction:'top'}});
        bounds.push([p.lat,p.lon]);
      }});
      if (bounds.length > 1) mapa.fitBounds(bounds, {{padding:[30,30], maxZoom:15}});
    </script>
    """, height=645)

init_db()
migrate_db()
aplicar_gps_desde_url()
scores = load_scores()

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

    # Brigadista fijo
    inspector = "Leinada Galvez"
    c1.text_input("Inspector / brigadista", value=inspector, disabled=True)

    # Folio automático y consecutivo
    with sqlite3.connect(DB_PATH) as con:
        row = con.execute(
            "SELECT COALESCE(MAX(id), 0) + 1 FROM inspecciones"
        ).fetchone()

    siguiente_id = int(row[0] or 1)
    folio = f"D12-{siguiente_id:06d}"
    c2.text_input("Folio", value=folio, disabled=True)

    domicilio = st.text_input("Domicilio")
    colonia = st.text_input("Colonia")

    st.markdown("### 📍 Ubicación del domicilio")
    ubicacion = st.text_input(
        "Referencia / ubicación",
        placeholder="Ej. Calle, colonia, referencia o punto de visita"
    )
    st.caption("Presiona OBTENER UBICACIÓN y permite el acceso al GPS del celular.")
    componentes_ubicacion()

    current_lat = st.session_state.get("lat_manual_d12")
    current_lon = st.session_state.get("lon_manual_d12")

    if current_lat is not None and current_lon is not None:
        st.success("📍 Ubicación obtenida correctamente.")
        c_lat, c_lon = st.columns(2)
        c_lat.metric("Latitud", f"{current_lat:.6f}")
        c_lon.metric("Longitud", f"{current_lon:.6f}")
        st.caption("Estas coordenadas se guardarán con esta encuesta.")
    else:
        st.info("📍 Todavía no hay una ubicación capturada.")

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
                      ubicacion, resultado, latitud, longitud
               FROM inspecciones
               WHERE latitud IS NOT NULL AND longitud IS NOT NULL
                     AND latitud != 0 AND longitud != 0
               ORDER BY id DESC""", con)

    mapa_ubicaciones_guardadas(mapa_guardado)
    if not mapa_guardado.empty:
        st.caption(f"📍 {len(mapa_guardado)} ubicaciones guardadas en el DISTRITO 12. Los puntos se conservan al guardar cada encuesta.")

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
