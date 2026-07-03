# -*- coding: utf-8 -*-
"""
Caciorgna Hotel — Gestionale prenotazioni per tre strutture.

Singola pagina scorrevole, ottimizzata per smartphone (in particolare iPhone),
con vista settimanale a griglia, inserimento prenotazioni, listino con deroghe
e calcolo incassi (giorno / settimana / mese / anno).

Avvio locale:  streamlit run app.py
Deploy:        compatibile con Streamlit Community Cloud (vedi note sul CSV).
"""

import os
import uuid
import base64
import hashlib
import urllib.parse
import datetime as dt
from calendar import monthrange

import pandas as pd
import streamlit as st

# Percorso dell'icona usata come favicon/scheda browser (se presente).
ICON_PATH = os.path.join("assets", "icon-192.png")
_page_icon = ICON_PATH if os.path.exists(ICON_PATH) else "🏨"

# =============================================================================
# 1. CONFIGURAZIONE PAGINA
# =============================================================================
# Nota: Streamlit accetta solo layout="centered" o "wide".
# "centered" è la scelta migliore per il mobile: limita la larghezza dei
# contenuti rendendoli pieni-schermo su iPhone ed eleganti su desktop.
st.set_page_config(
    page_title="Caciorgna Hotels",
    page_icon=_page_icon,
    layout="centered",
    initial_sidebar_state="collapsed",
)

# =============================================================================
# 2. COSTANTI: STRUTTURE, CAMERE E LISTINO PREZZI
# =============================================================================
# Tipi di camera usati internamente:
#   "doppia"      -> usabile come singola o doppia
#   "tripla"      -> usabile come singola, doppia o tripla
#   "tripla_quad" -> come la tripla ma usabile anche come quadrupla (camera 27)

# --- Hotel Il Faro: camere 11-27 (17 totali) ---------------------------------
# 12 doppie + 5 triple. Le triple sono le camere 12, 17, 18, 19 e 27;
# la 27 è una tripla utilizzabile anche come quadrupla.
_faro_rooms = {
    11: "doppia",
    12: "tripla",
    13: "doppia",
    14: "doppia",
    15: "doppia",
    16: "doppia",
    17: "tripla",
    18: "tripla",
    19: "tripla",
    20: "doppia",
    21: "doppia",
    22: "doppia",
    23: "doppia",
    24: "doppia",
    25: "doppia",
    26: "doppia",
    27: "tripla_quad",  # tripla utilizzabile anche come quadrupla
}

HOTELS = {
    "Hotel Il Faro": {
        "icona": "🗼",
        "rooms": _faro_rooms,
        # Listino giornaliero per tipo di USO
        "prezzi": {"Singola": 45, "Doppia": 60, "Tripla": 75, "Quadrupla": 90},
    },
    "Palazzo Caciorgna": {
        "icona": "🏛️",
        # 5 camere: 2 doppie (1-2) + 3 triple (3-5)
        "rooms": {1: "doppia", 2: "doppia", 3: "tripla", 4: "tripla", 5: "tripla"},
        "prezzi": {"Singola": 50, "Doppia": 70, "Tripla": 90},
    },
    "Villa del Cavaliere": {
        "icona": "🏰",
        # 6 camere: 5 doppie + 1 tripla (la tripla è la camera 1)
        "rooms": {1: "tripla", 2: "doppia", 3: "doppia", 4: "doppia", 5: "doppia", 6: "doppia"},
        "prezzi": {"Singola": 50, "Doppia": 70, "Tripla": 80},
    },
}

# Opzioni di "uso" ammesse in base al tipo fisico della camera.
USI_PER_TIPO = {
    "doppia": ["Singola", "Doppia"],
    "tripla": ["Singola", "Doppia", "Tripla"],
    "tripla_quad": ["Singola", "Doppia", "Tripla", "Quadrupla"],
}

# Etichetta breve del tipo camera (mostrata in griglia).
TIPO_LABEL = {"doppia": "Doppia", "tripla": "Tripla", "tripla_quad": "Tripla/Quad"}

# File di salvataggio persistente.
DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "prenotazioni.csv")

# Password di accesso: NON è nel codice. Va impostata nei Secrets di Streamlit
# (chiave "password") oppure nella variabile d'ambiente APP_PASSWORD in locale.

# Colonne del CSV / dei record prenotazione.
COLONNE = [
    "id", "hotel", "camera", "tipo_camera", "uso",
    "check_in", "check_out", "tipo_cliente", "intestatario",
    "telefono", "email", "prezzo_notte", "prezzo_standard", "deroga",
    "note", "creato_il",
]

# Giorni della settimana in italiano (abbreviati).
GIORNI_IT = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
MESI_IT = [
    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]


# =============================================================================
# 3. STILE (CSS) — identità visiva e ottimizzazione mobile
# =============================================================================
@st.cache_data(show_spinner=False)
def _watermark_uri():
    """Carica la filigrana (assets/watermark.png) come data URI. Vuoto se assente."""
    try:
        with open(os.path.join("assets", "watermark.png"), "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()
    except Exception:
        return ""


def inietta_css():
    """Inietta il foglio di stile globale (font, palette, griglia, card).

    Lo stile è 'mobile-first': dimensioni compatte di default e una media query
    che amplia spazi e font su schermi larghi (desktop/laptop).
    """
    css = """
<style>
/* --- Tipografia: display serif + sans pulito (Google Fonts) --- */
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&display=swap');

:root{
  /* Tema AS Roma: rosso + oro su sfondo giallo caldo */
  --marine:#8E1F2F; --marine-2:#6E1422; --ottone:#F4C13C;
  --avorio:#FBF1D4; --inchiostro:#2a1d12;
  --libera:#2E8B6B; --occupata:#8E1F2F;
}

/* Sfondo, font e COLORE testo imposti sul container: garantiscono leggibilità
   anche se l'app non carica il tema (niente più testo bianco su bianco). */
[data-testid="stAppViewContainer"]{
  background:linear-gradient(160deg,#FBF1D4 0%,#FCF6E4 45%,#FBE3DA 100%);
  color:var(--inchiostro);
  font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
}
/* IMPORTANTE: non sovrascrivere il font delle icone di Streamlit, altrimenti
   le frecce degli expander compaiono come testo ("arrow_down"). Le ri-forzo. */
[data-testid="stIconMaterial"], [data-testid="stExpanderToggleIcon"],
span.material-icons, span.material-symbols-rounded, span.material-symbols-outlined,
[class*="material-symbols"], [class*="material-icons"]{
  font-family:'Material Symbols Rounded','Material Symbols Outlined','Material Icons' !important;
}
/* Etichette dei widget e testo digitato: sempre scuri e leggibili */
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label,
div[data-testid="stForm"] label, .stCheckbox label, .stRadio label{
  color:var(--inchiostro) !important; font-weight:600;
}
.stDateInput input, .stTextInput input, .stNumberInput input,
.stTextArea textarea, .stSelectbox div[data-baseweb="select"]{
  color:var(--inchiostro) !important;
}
.stDateInput input, .stTextInput input, .stNumberInput input, .stTextArea textarea{
  background:#fff !important;
}
.block-container{ padding-top:1.4rem; padding-bottom:3rem; max-width:820px; }

/* --- Testata --- */
.app-header{
  background:linear-gradient(160deg,#a3293a 0%,var(--marine) 45%,var(--marine-2) 100%);
  border-radius:20px; padding:34px 24px 28px; margin:0 0 22px; text-align:center;
  box-shadow:0 12px 32px rgba(110,20,34,.28); border:1.5px solid rgba(244,193,60,.55);
}
.app-header h1{
  font-family:'Fraunces',serif; color:#fff; font-size:44px; font-weight:700;
  margin:0; line-height:1.08; letter-spacing:.4px;
}
.app-header h1 .acc{ color:var(--ottone); }
.app-header .rule{
  width:66px; height:3px; background:var(--ottone); border-radius:3px; margin:14px auto 12px;
}
.app-header .pedice{
  color:#f3d79b; font-size:13px; font-weight:600; text-transform:uppercase;
  letter-spacing:2.6px; line-height:1.5; margin:0;
}
@media (max-width:560px){
  .app-header{ padding:26px 18px 22px; }
  .app-header h1{ font-size:33px; }
  .app-header .pedice{ font-size:10.5px; letter-spacing:1.6px; }
}

/* --- Card KPI incassi: griglia 2 colonne su mobile, 4 su desktop --- */
.kpi-grid{ display:grid; grid-template-columns:repeat(2,1fr); gap:10px; margin:2px 0 18px; }
.kpi-card{
  background:#fff; border:1px solid #ece5d8; border-left:5px solid var(--ottone);
  border-radius:14px; padding:13px 15px; box-shadow:0 2px 8px rgba(27,43,52,.05);
}
.kpi-card .etichetta{
  font-size:11px; text-transform:uppercase; letter-spacing:1px;
  color:#7b746a; font-weight:600; line-height:1.3; margin:0;
}
.kpi-card .valore{
  font-family:'Fraunces',serif; font-size:25px; font-weight:700;
  color:var(--marine); line-height:1.2; margin:4px 0 0; white-space:nowrap;
}

/* --- Titolo struttura --- */
.hotel-titolo{
  font-family:'Fraunces',serif; font-size:21px; font-weight:600; color:var(--marine);
  margin:24px 0 4px; padding-bottom:7px; border-bottom:2px solid var(--ottone); line-height:1.25;
}
.hotel-meta{ font-size:12.5px; color:#7b746a; margin:0 0 12px; line-height:1.4; }

/* --- Griglia settimanale (layout flex, allineamento perfetto) --- */
.grid-wrap{
  overflow-x:auto; -webkit-overflow-scrolling:touch; border-radius:14px;
  border:1px solid #ece5d8; background:#fff; box-shadow:0 2px 8px rgba(27,43,52,.05);
  margin-bottom:8px;
}
.grid-inner{ display:flex; flex-direction:column; gap:6px; padding:10px; min-width:560px; }
.grow{ display:flex; gap:6px; align-items:stretch; }
/* Colonna camera (a sinistra, resta visibile durante lo scroll orizzontale) */
.rc, .rch{ flex:0 0 84px; position:sticky; left:0; z-index:3; background:#fff; }
.rch{ font-size:11px; font-weight:600; color:#5b5750; display:flex; align-items:flex-end; padding:0 0 4px 4px; }
.rc{
  font-size:12.5px; font-weight:700; color:var(--marine); line-height:1.15;
  display:flex; flex-direction:column; justify-content:center; padding-left:4px;
  border-right:1px solid #eee;
}
.rc small{ color:#9a948a; font-weight:500; font-size:10px; line-height:1.2; }
/* Intestazioni giorni */
.dh{
  flex:1 1 0; min-width:56px; text-align:center; font-size:11px; font-weight:600;
  color:#5b5750; line-height:1.2; padding-bottom:2px;
}
.dh b{ font-weight:700; color:var(--inchiostro); }
/* Celle giorno: ora sono link cliccabili con effetto 3D al tocco/click */
.dc{ flex:1 1 0; min-width:56px; display:flex; }
.cell{
  flex:1; border-radius:10px; text-align:center; color:#fff !important; font-weight:600;
  padding:8px 4px; line-height:1.15; display:flex; flex-direction:column;
  justify-content:center; min-height:44px; cursor:pointer; text-decoration:none !important;
  user-select:none; -webkit-tap-highlight-color:transparent;
  box-shadow:0 3px 0 rgba(0,0,0,.30), 0 4px 9px rgba(0,0,0,.14);
  transition:transform .07s ease, box-shadow .07s ease, filter .12s ease;
}
.cell.free{ background:linear-gradient(180deg,#37a37c 0%,#2E8B6B 100%); font-size:11px; }
.cell.occ{ background:linear-gradient(180deg,#a3293a 0%,#8E1F2F 100%); }
/* Giorno di CHECK-IN: spessa barra verticale gialla neon a sinistra (stacco di inizio) */
.cell.occ.checkin{
  box-shadow:inset 6px 0 0 0 #E5FF00, 0 3px 0 rgba(0,0,0,.30), 0 4px 9px rgba(0,0,0,.14);
}
.cell:hover{ filter:brightness(1.07); }
.cell:active{                                   /* premuto: si abbassa */
  transform:translateY(3px);
  box-shadow:0 0 0 rgba(0,0,0,.30), 0 1px 3px rgba(0,0,0,.12);
}
.cell .nome{
  font-weight:700; font-size:10.5px; white-space:nowrap; overflow:hidden;
  text-overflow:ellipsis; max-width:100%;
}
.cell .uso{ font-size:9px; opacity:.92; font-weight:500; margin-top:1px; }

/* Riepilogo libere/occupate */
.occ-sum{ font-size:12.5px; color:#5b5750; margin:2px 2px 6px; line-height:1.4; }
.occ-sum b.lib{ color:var(--libera); } .occ-sum b.occ{ color:var(--occupata); }

/* Bottoni e form in tinta */
.stButton>button{ border-radius:10px; font-weight:600; }
/* Larghezza piena dei pulsanti via CSS (al posto del deprecato use_container_width) */
.stButton>button, .stDownloadButton>button,
[data-testid="stFormSubmitButton"]>button, [data-testid="stBaseButton-secondaryFormSubmit"]{
  width:100%;
}
div[data-testid="stForm"]{ border:1px solid #ece5d8; border-radius:14px; background:#fff; }

/* Tabelle dello storico: piena larghezza e intestazioni in tinta */
[data-testid="stTable"] table{ width:100%; font-size:13px; }
[data-testid="stTable"] th{ color:var(--marine); font-weight:700; }
[data-testid="stTable"] td, [data-testid="stTable"] th{ padding:6px 10px; }

/* --- Tasto HOME fisso, sempre visibile (in basso a SINISTRA, per non finire
       sotto il badge "Gestisci l'app" di Streamlit Cloud che sta a destra) --- */
.home-fab{
  position:fixed; left:18px; bottom:18px; z-index:99999;
  background:linear-gradient(180deg,#a3293a 0%,#6E1422 100%); color:#fff !important;
  font-weight:700; font-size:14px; text-decoration:none !important;
  padding:12px 18px; border-radius:30px; line-height:1;
  box-shadow:0 6px 18px rgba(110,20,34,.4); border:1.5px solid var(--ottone);
  display:inline-flex; align-items:center; gap:7px; -webkit-tap-highlight-color:transparent;
  transition:transform .07s ease, box-shadow .07s ease, filter .12s ease;
}
.home-fab:hover{ filter:brightness(1.12); }
.home-fab:active{ transform:translateY(2px); box-shadow:0 2px 8px rgba(15,42,58,.38); }
@media (max-width:560px){
  .home-fab{ left:14px; bottom:14px; padding:11px 15px; font-size:13px; }
}

/* --- Barre delle sezioni (expander) EVIDENTI e in 3D --- */
[data-testid="stExpander"]{ border:none !important; background:transparent !important; }
[data-testid="stExpander"] details{ border:none !important; background:transparent !important; }
[data-testid="stExpander"] summary, .streamlit-expanderHeader{
  background:linear-gradient(180deg,#a3293a 0%, #8E1F2F 100%);
  border:1.6px solid var(--ottone); border-radius:14px;
  padding:15px 16px; margin-bottom:6px; cursor:pointer;
  box-shadow:0 5px 0 #5a0f18, 0 9px 16px rgba(0,0,0,.26);
  transition:transform .08s ease, box-shadow .08s ease, filter .12s ease;
}
[data-testid="stExpander"] summary:hover{ filter:brightness(1.06); }
[data-testid="stExpander"] summary:active{
  transform:translateY(4px);
  box-shadow:0 1px 0 #5a0f18, 0 3px 8px rgba(0,0,0,.26);
}
[data-testid="stExpander"] summary p{
  font-weight:700 !important; font-size:16.5px !important; color:var(--ottone) !important;
}
[data-testid="stExpander"] summary svg,
[data-testid="stExpander"] summary [data-testid="stIconMaterial"]{ color:var(--ottone) !important; }

/* --- Desktop / laptop: più respiro e font leggermente maggiori --- */
@media (min-width:680px){
  .kpi-grid{ grid-template-columns:repeat(4,1fr); }
  .kpi-card .valore{ font-size:27px; }
  .grid-inner{ min-width:0; }            /* su desktop entra tutto, niente scroll */
  .dh, .dc{ min-width:64px; }
}
</style>
"""
    st.markdown(css, unsafe_allow_html=True)

    # --- Filigrana (logo Villa del Cavaliere) tenue ed elegante, dietro ogni sezione ---
    wm = _watermark_uri()
    if wm:
        st.markdown(
            f'<style>'
            f'[data-testid="stAppViewContainer"]::before{{'
            f'content:""; position:fixed; inset:0; z-index:0; pointer-events:none;'
            f'background-image:url("{wm}"); background-repeat:no-repeat;'
            f'background-position:center 46%; background-size:min(520px,74vw); opacity:.06;}}'
            f'[data-testid="stAppViewContainer"] .block-container{{ position:relative; z-index:1; }}'
            f'</style>',
            unsafe_allow_html=True,
        )


# =============================================================================
# 4. PERSISTENZA DEI DATI (CSV + session_state)
# =============================================================================
def carica_prenotazioni():
    """Carica le prenotazioni dal CSV (se esiste) come lista di dizionari."""
    if os.path.exists(DATA_FILE):
        try:
            df = pd.read_csv(DATA_FILE, dtype=str).fillna("")
            records = df.to_dict("records")
            # Conversione dei tipi (CSV salva tutto come stringa).
            for r in records:
                r["camera"] = int(float(r["camera"]))
                r["prezzo_notte"] = float(r["prezzo_notte"])
                r["prezzo_standard"] = float(r.get("prezzo_standard") or 0)
                r["deroga"] = str(r.get("deroga")).lower() in ("true", "1", "vero")
            return records
        except Exception as e:
            st.warning(f"Impossibile leggere il file dati: {e}")
            return []
    return []


def salva_prenotazioni():
    """Scrive su CSV lo stato corrente delle prenotazioni (salvataggio persistente)."""
    os.makedirs(DATA_DIR, exist_ok=True)
    df = pd.DataFrame(st.session_state.prenotazioni, columns=COLONNE)
    df.to_csv(DATA_FILE, index=False)


# =============================================================================
# 5. FUNZIONI DI SUPPORTO (date, prezzi, occupazione, incassi)
# =============================================================================
def a_data(s):
    """Converte una stringa ISO (YYYY-MM-DD) in oggetto date."""
    if isinstance(s, dt.date):
        return s
    return dt.date.fromisoformat(str(s))


def inizio_settimana(d):
    """Restituisce il lunedì della settimana che contiene la data d."""
    return d - dt.timedelta(days=d.weekday())


def giorni_settimana(d):
    """Lista dei 7 giorni (lun->dom) della settimana che contiene d."""
    lun = inizio_settimana(d)
    return [lun + dt.timedelta(days=i) for i in range(7)]


def prezzo_standard(hotel, uso):
    """Tariffa standard a notte per un certo uso nella struttura indicata."""
    return float(HOTELS[hotel]["prezzi"].get(uso, 0))


def camera_occupata_il(hotel, camera, giorno):
    """Restituisce la prenotazione che occupa hotel/camera in quel giorno, o None.

    Convenzione alberghiera: si pagano le notti da check_in (incluso) a
    check_out (escluso). Il giorno di check_out la camera torna libera.
    """
    for p in st.session_state.prenotazioni:
        if p["hotel"] == hotel and int(p["camera"]) == int(camera):
            if a_data(p["check_in"]) <= giorno < a_data(p["check_out"]):
                return p
    return None


def c_e_sovrapposizione(hotel, camera, check_in, check_out, escludi_id=None):
    """True se esiste già una prenotazione che si sovrappone alle date indicate."""
    for p in st.session_state.prenotazioni:
        if escludi_id and p["id"] == escludi_id:
            continue
        if p["hotel"] == hotel and int(p["camera"]) == int(camera):
            if a_data(p["check_in"]) < check_out and check_in < a_data(p["check_out"]):
                return True
    return False


def incasso_intervallo(inizio, fine):
    """Incasso totale nelle notti comprese in [inizio, fine) (fine esclusa)."""
    totale = 0.0
    for p in st.session_state.prenotazioni:
        ci, co = a_data(p["check_in"]), a_data(p["check_out"])
        s = max(ci, inizio)
        e = min(co, fine)
        notti = (e - s).days
        if notti > 0:
            totale += notti * float(p["prezzo_notte"])
    return totale


def euro(x):
    """Formatta un importo in stile italiano: 1.234 €."""
    return f"{x:,.0f} €".replace(",", ".")


def incasso_mese(anno, mese):
    """Incasso totale di un mese specifico."""
    primo = dt.date(anno, mese, 1)
    ultimo = monthrange(anno, mese)[1]
    return incasso_intervallo(primo, primo + dt.timedelta(days=ultimo))


def incasso_anno(anno):
    """Incasso totale di un anno specifico."""
    return incasso_intervallo(dt.date(anno, 1, 1), dt.date(anno + 1, 1, 1))


def anni_con_dati():
    """Elenco ordinato degli anni (>=2026) presenti nelle prenotazioni + anno corrente."""
    anni = set()
    for p in st.session_state.prenotazioni:
        anni.add(a_data(p["check_in"]).year)
        anni.add((a_data(p["check_out"]) - dt.timedelta(days=1)).year)
    oggi = dt.date.today()
    anni.add(oggi.year if oggi.year >= 2026 else 2026)
    return sorted(a for a in anni if a >= 2026)


# =============================================================================
# 6. COSTRUZIONE HTML DELLA GRIGLIA SETTIMANALE
# =============================================================================
def abbrevia(nome, n=9):
    """Abbrevia un nome lungo per la cella (con puntini di sospensione)."""
    nome = (nome or "").strip()
    return nome if len(nome) <= n else nome[: n - 1] + "…"


def griglia_hotel_html(hotel, settimana):
    """Genera la griglia HTML (verde=libera / rosso=occupata) per una struttura.

    Layout a flex: ogni riga ha la stessa struttura (label camera + 7 celle giorno),
    quindi le colonne risultano sempre allineate. L'HTML è prodotto su riga singola
    per evitare che Streamlit/Markdown lo interpreti come blocco di codice.
    """
    rooms = HOTELS[hotel]["rooms"]
    parti = ['<div class="grid-wrap"><div class="grid-inner">']

    # Riga di intestazione (angolo + 7 giorni).
    parti.append('<div class="grow"><div class="rch">Camera</div>')
    for d in settimana:
        parti.append(f'<div class="dh">{GIORNI_IT[d.weekday()]}<br><b>{d.strftime("%d/%m")}</b></div>')
    parti.append("</div>")

    # Una riga per camera.
    qh = urllib.parse.quote(hotel)
    aq = _auth_qs()  # token che mantiene l'accesso attraverso i ricaricamenti
    for camera, tipo in rooms.items():
        parti.append(f'<div class="grow"><div class="rc">N. {camera}<small>{TIPO_LABEL[tipo]}</small></div>')
        for d in settimana:
            p = camera_occupata_il(hotel, camera, d)
            if p:
                # Cella ROSSA -> link che apre la MODIFICA di quella prenotazione.
                nome = abbrevia(p["intestatario"])
                href = f"?act=edit&id={p['id']}{aq}"
                # Se è il giorno di CHECK-IN, aggiungo la barra gialla neon a sinistra.
                extra = " checkin" if a_data(p["check_in"]) == d else ""
                parti.append(
                    f'<div class="dc"><a class="cell occ{extra}" target="_self" href="{href}" '
                    f'title="{p["intestatario"]} — {p["uso"]} (tocca per modificare)">'
                    f'<span class="nome">{nome}</span><span class="uso">{p["uso"]}</span></a></div>'
                )
            else:
                # Cella VERDE -> link che apre l'INSERIMENTO per camera/giorno.
                href = f"?act=add&h={qh}&r={camera}&d={d.isoformat()}{aq}"
                parti.append(
                    f'<div class="dc"><a class="cell free" target="_self" href="{href}" '
                    f'title="Tocca per prenotare la N. {camera} il {d.strftime("%d/%m")}">libera</a></div>'
                )
        parti.append("</div>")

    parti.append("</div></div>")
    return "".join(parti)


# =============================================================================
# 7. INIZIALIZZAZIONE STATO
# =============================================================================
def init_stato():
    if "prenotazioni" not in st.session_state:
        st.session_state.prenotazioni = carica_prenotazioni()


# =============================================================================
# 8. SEZIONI DELL'INTERFACCIA
# =============================================================================
def sezione_testata():
    st.markdown(
        '<div class="app-header">'
        '<h1>Caciorgna <span class="acc">Hotels</span></h1>'
        '<div class="rule"></div>'
        '<div class="pedice">Il Faro · Palazzo Caciorgna · Villa del Cavaliere</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def sezione_kpi(giorno):
    """Calcola e mostra i 4 KPI di incasso: oggi / settimana selezionata /
    mese e anno della settimana selezionata."""
    sett = giorni_settimana(giorno)
    lun, dom_next = sett[0], sett[-1] + dt.timedelta(days=1)

    # Mese e anno della settimana selezionata (basati sul lunedì).
    primo_mese = giorno.replace(day=1)
    ultimo_giorno = monthrange(giorno.year, giorno.month)[1]
    fine_mese = primo_mese + dt.timedelta(days=ultimo_giorno)
    primo_anno = dt.date(giorno.year, 1, 1)
    fine_anno = dt.date(giorno.year + 1, 1, 1)

    # Il primo KPI è l'incasso di OGGI (giorno reale), non del giorno selezionato,
    # perché ora il selettore rappresenta la settimana.
    oggi = dt.date.today()
    inc_oggi = incasso_intervallo(oggi, oggi + dt.timedelta(days=1))
    inc_sett = incasso_intervallo(lun, dom_next)
    inc_mese = incasso_intervallo(primo_mese, fine_mese)
    inc_anno = incasso_intervallo(primo_anno, fine_anno)

    st.markdown(
        '<div class="kpi-grid">'
        f'<div class="kpi-card"><p class="etichetta">Oggi {oggi.strftime("%d/%m")}</p><p class="valore">{euro(inc_oggi)}</p></div>'
        f'<div class="kpi-card"><p class="etichetta">Settimana</p><p class="valore">{euro(inc_sett)}</p></div>'
        f'<div class="kpi-card"><p class="etichetta">{MESI_IT[giorno.month - 1]}</p><p class="valore">{euro(inc_mese)}</p></div>'
        f'<div class="kpi-card"><p class="etichetta">Anno {giorno.year}</p><p class="valore">{euro(inc_anno)}</p></div>'
        '</div>',
        unsafe_allow_html=True,
    )


def sezione_form_prenotazione(giorno_default):
    """Form dedicato per inserire una nuova prenotazione.

    Si apre automaticamente (già precompilato) quando si tocca una cella VERDE
    nella griglia, oppure manualmente dall'expander.
    """
    apri = st.session_state.get("open_add", False)
    with st.expander("➕  Aggiungi prenotazione", expanded=apri):
        if apri:
            st.info(
                f"Nuova prenotazione per **{st.session_state.get('f_hotel','')} — "
                f"N. {st.session_state.get('f_camera','')}**. Completa i dati e salva."
            )
        # --- Selettori e deroga FUORI dal form ---
        # Devono reagire subito al tocco: l'elenco usi, il prezzo standard e la
        # deroga dipendono dalle scelte e dentro un st.form non si aggiornerebbero
        # finché non si invia.
        c1, c2 = st.columns(2)
        hotel = c1.selectbox("Struttura", list(HOTELS.keys()), key="f_hotel")
        rooms = HOTELS[hotel]["rooms"]
        # Se cambio struttura, riallineo la camera a una valida per evitare errori.
        if st.session_state.get("f_camera") not in rooms:
            st.session_state["f_camera"] = list(rooms.keys())[0]
        camera = c2.selectbox(
            "Camera",
            list(rooms.keys()),
            format_func=lambda n: f"N. {n} ({TIPO_LABEL[rooms[n]]})",
            key="f_camera",
        )
        tipo = rooms[camera]
        usi = USI_PER_TIPO[tipo]
        if st.session_state.get("f_uso") not in usi:
            st.session_state["f_uso"] = usi[0]
        uso = st.selectbox("Tipo di uso", usi, key="f_uso")

        prezzo_std = prezzo_standard(hotel, uso)

        # --- Deroga prezzo (±1€ a tocco) ---
        applica_deroga = st.checkbox(
            "Deroga prezzo standard (modifica manuale a 1 € per tocco)",
            key="f_deroga",
        )
        if applica_deroga:
            # La key cambia con hotel/camera/uso: così il campo riparte sempre
            # dalla tariffa standard corretta quando cambi la selezione.
            prezzo_notte = st.number_input(
                "Prezzo a notte (€)",
                min_value=0.0, step=1.0, format="%.0f",
                value=float(prezzo_std),
                key=f"f_prezzo_{hotel}_{camera}_{uso}",
            )
            st.caption(
                f"Standard {euro(prezzo_std)} → applicato **{euro(prezzo_notte)}**"
            )
        else:
            prezzo_notte = prezzo_std
            st.caption(f"Tariffa standard a notte: **{euro(prezzo_std)}**")

        # --- Dati cliente e date DENTRO il form ---
        # Le date partono dal giorno cliccato sulla griglia (se presente).
        ci_default = st.session_state.get("add_ci", giorno_default)
        co_default = st.session_state.get("add_co", ci_default + dt.timedelta(days=1))
        with st.form("form_prenotazione", clear_on_submit=True):
            c3, c4 = st.columns(2)
            check_in = c3.date_input(
                "Data check-in", value=ci_default,
                min_value=dt.date(2026, 1, 1), format="DD/MM/YYYY",
            )
            check_out = c4.date_input(
                "Data check-out", value=co_default,
                min_value=dt.date(2026, 1, 1), format="DD/MM/YYYY",
            )

            tipo_cliente = st.radio(
                "Tipologia cliente", ["Privato", "Ditta"],
                horizontal=True, key="f_tipo_cliente",
            )
            intestatario = st.text_input(
                "Cognome e Nome  /  Ragione sociale", key="f_intestatario",
                placeholder="Es. Rossi Mario  oppure  Rossi S.r.l.",
            )

            c5, c6 = st.columns(2)
            telefono = c5.text_input("Telefono", key="f_tel", placeholder="+39 ...")
            email = c6.text_input("Email", key="f_email", placeholder="nome@dominio.it")

            note = st.text_area("Note (facoltative)", key="f_note", height=70)

            inviato = st.form_submit_button("💾  Salva prenotazione")

        if inviato:
            # --- Validazioni ---
            if not intestatario.strip():
                st.error("Inserisci il nominativo o la ragione sociale.")
                return
            if check_out <= check_in:
                st.error("Il check-out deve essere successivo al check-in.")
                return
            if c_e_sovrapposizione(hotel, camera, check_in, check_out):
                st.error(
                    f"La camera N. {camera} di {hotel} è già prenotata in queste date."
                )
                return

            nuova = {
                "id": uuid.uuid4().hex[:8],
                "hotel": hotel,
                "camera": int(camera),
                "tipo_camera": tipo,
                "uso": uso,
                "check_in": check_in.isoformat(),
                "check_out": check_out.isoformat(),
                "tipo_cliente": tipo_cliente,
                "intestatario": intestatario.strip(),
                "telefono": telefono.strip(),
                "email": email.strip(),
                "prezzo_notte": float(prezzo_notte),
                "prezzo_standard": prezzo_std,
                "deroga": bool(applica_deroga),
                "note": note.strip(),
                "creato_il": dt.datetime.now().isoformat(timespec="seconds"),
            }
            st.session_state.prenotazioni.append(nuova)
            salva_prenotazioni()
            # Chiudo il pannello di aggiunta e pulisco i prefill da click sulla griglia.
            for k in ("open_add", "add_ci", "add_co"):
                st.session_state.pop(k, None)
            notti = (check_out - check_in).days
            st.success(
                f"Prenotazione salvata: {intestatario.strip()} — N. {camera} "
                f"({uso}), {notti} notti, totale {euro(notti * float(prezzo_notte))}."
            )


def sezione_griglie(giorno):
    """Mostra, struttura per struttura, la griglia settimanale verde/rosso."""
    settimana = giorni_settimana(giorno)
    lun, dom = settimana[0], settimana[-1]
    st.markdown(
        f"#### 📅 Settimana dal {lun.strftime('%d/%m/%Y')} al {dom.strftime('%d/%m/%Y')}"
    )

    for hotel, conf in HOTELS.items():
        rooms = conf["rooms"]
        n_doppie = sum(1 for t in rooms.values() if t == "doppia")
        n_triple = sum(1 for t in rooms.values() if t.startswith("tripla"))

        st.markdown(
            f'<div class="hotel-titolo">{conf["icona"]} {hotel}</div>'
            f'<div class="hotel-meta">{len(rooms)} camere · {n_doppie} doppie · {n_triple} triple</div>',
            unsafe_allow_html=True,
        )
        st.markdown(griglia_hotel_html(hotel, settimana), unsafe_allow_html=True)

        # Riepilogo libere/occupate per il giorno selezionato.
        occupate = sum(
            1 for c in rooms if camera_occupata_il(hotel, c, giorno) is not None
        )
        libere = len(rooms) - occupate
        st.markdown(
            f'<div class="occ-sum">Il {giorno.strftime("%d/%m")}: '
            f'<b class="lib">{libere} libere</b> · <b class="occ">{occupate} occupate</b></div>',
            unsafe_allow_html=True,
        )


def _chiudi_modifica():
    """Pulisce lo stato del form di modifica."""
    for k in [
        "edit_id", "_edit_seed", "e_prev_combo", "e_hotel", "e_camera", "e_uso", "e_deroga",
        "e_prezzo", "e_in", "e_out", "e_tcli", "e_int", "e_tel", "e_email", "e_note",
    ]:
        st.session_state.pop(k, None)


def _form_modifica(pid):
    """Form di modifica (prefilled) per la prenotazione con id = pid."""
    p = next((x for x in st.session_state.prenotazioni if x["id"] == pid), None)
    if p is None:
        _chiudi_modifica()
        return

    # Pre-carica i valori una sola volta (alla prima apertura su questa prenotazione).
    if st.session_state.get("_edit_seed") != pid:
        st.session_state.e_hotel = p["hotel"]
        st.session_state.e_camera = int(p["camera"])
        st.session_state.e_uso = p["uso"]
        st.session_state.e_deroga = bool(p["deroga"])
        st.session_state.e_prezzo = float(p["prezzo_notte"])
        st.session_state.e_in = a_data(p["check_in"])
        st.session_state.e_out = a_data(p["check_out"])
        st.session_state.e_tcli = p["tipo_cliente"] if p["tipo_cliente"] in ("Privato", "Ditta") else "Privato"
        st.session_state.e_int = p["intestatario"]
        st.session_state.e_tel = p["telefono"]
        st.session_state.e_email = p["email"]
        st.session_state.e_note = p.get("note", "")
        st.session_state.e_prev_combo = (p["hotel"], int(p["camera"]), p["uso"])
        st.session_state._edit_seed = pid

    st.caption(f"Stai modificando la prenotazione di **{p['intestatario']}**.")

    c1, c2 = st.columns(2)
    hotel = c1.selectbox("Struttura", list(HOTELS.keys()), key="e_hotel")
    rooms = HOTELS[hotel]["rooms"]
    # Se l'hotel è cambiato, riallineo la camera a una valida (accesso SICURO con .get).
    if st.session_state.get("e_camera") not in rooms:
        st.session_state["e_camera"] = list(rooms.keys())[0]
    camera = c2.selectbox(
        "Camera", list(rooms.keys()),
        format_func=lambda n: f"N. {n} ({TIPO_LABEL[rooms[n]]})", key="e_camera",
    )
    tipo = rooms[camera]
    usi = USI_PER_TIPO[tipo]
    if st.session_state.get("e_uso") not in usi:
        st.session_state["e_uso"] = usi[0]
    uso = st.selectbox("Tipo di uso", usi, key="e_uso")

    prezzo_std = prezzo_standard(hotel, uso)
    # Prezzo precompilato col valore attuale della prenotazione; quando cambi
    # struttura/camera/uso si AGGIORNA automaticamente alla nuova tariffa standard
    # (poi resta modificabile manualmente a 1 € per tocco).
    combo = (hotel, int(camera), uso)
    if "e_prezzo" not in st.session_state:
        st.session_state["e_prezzo"] = float(p["prezzo_notte"])
    elif st.session_state.get("e_prev_combo") != combo:
        st.session_state["e_prezzo"] = float(prezzo_std)
    st.session_state["e_prev_combo"] = combo
    prezzo_notte = st.number_input(
        "Prezzo a notte (€) — modificabile a 1 € per tocco",
        min_value=0.0, step=1.0, format="%.0f", key="e_prezzo",
    )
    deroga = abs(float(prezzo_notte) - prezzo_std) > 1e-9
    if deroga:
        st.caption(f"Tariffa standard {euro(prezzo_std)} → **deroga applicata: {euro(prezzo_notte)}**")
    else:
        st.caption(f"Tariffa standard a notte: {euro(prezzo_std)}")

    c3, c4 = st.columns(2)
    check_in = c3.date_input("Data check-in", min_value=dt.date(2026, 1, 1), format="DD/MM/YYYY", key="e_in")
    check_out = c4.date_input("Data check-out", min_value=dt.date(2026, 1, 1), format="DD/MM/YYYY", key="e_out")
    tipo_cliente = st.radio("Tipologia cliente", ["Privato", "Ditta"], horizontal=True, key="e_tcli")
    intestatario = st.text_input("Cognome e Nome  /  Ragione sociale", key="e_int")
    c5, c6 = st.columns(2)
    telefono = c5.text_input("Telefono", key="e_tel")
    email = c6.text_input("Email", key="e_email")
    note = st.text_area("Note (facoltative)", key="e_note", height=70)

    b1, b2 = st.columns(2)
    salva = b1.button("✅  Salva modifiche", key="e_save")
    annulla = b2.button("✖️  Annulla", key="e_cancel")

    if annulla:
        _chiudi_modifica()
        st.rerun()

    if salva:
        if not intestatario.strip():
            st.error("Inserisci il nominativo o la ragione sociale.")
            return
        if check_out <= check_in:
            st.error("Il check-out deve essere successivo al check-in.")
            return
        if c_e_sovrapposizione(hotel, camera, check_in, check_out, escludi_id=pid):
            st.error(f"La camera N. {camera} di {hotel} è già prenotata in queste date.")
            return

        p.update({
            "hotel": hotel, "camera": int(camera), "tipo_camera": tipo, "uso": uso,
            "check_in": check_in.isoformat(), "check_out": check_out.isoformat(),
            "tipo_cliente": tipo_cliente, "intestatario": intestatario.strip(),
            "telefono": telefono.strip(), "email": email.strip(),
            "prezzo_notte": float(prezzo_notte), "prezzo_standard": prezzo_std,
            "deroga": bool(deroga), "note": note.strip(),
        })
        salva_prenotazioni()
        _chiudi_modifica()
        st.success("Modifiche salvate.")
        st.rerun()


def sezione_modifica():
    """Mostra il modulo di modifica in alto (compare cliccando una cella rossa
    o il tasto Modifica nella gestione)."""
    if not st.session_state.get("edit_id"):
        return
    with st.container(border=True):
        st.markdown("### ✏️ Modifica prenotazione")
        _form_modifica(st.session_state.edit_id)


def sezione_gestione():
    """Elenco prenotazioni con modifica ed eliminazione."""
    with st.expander("📋  Prenotazioni registrate", expanded=False):
        prenotazioni = st.session_state.prenotazioni
        if not prenotazioni:
            st.info("Nessuna prenotazione registrata.")
            return

        # Tabella riassuntiva.
        righe = []
        for p in sorted(prenotazioni, key=lambda x: a_data(x["check_in"])):
            notti = (a_data(p["check_out"]) - a_data(p["check_in"])).days
            righe.append({
                "Struttura": p["hotel"],
                "Camera": f'N. {p["camera"]}',
                "Uso": p["uso"] + (" (deroga)" if p["deroga"] else ""),
                "Intestatario": p["intestatario"],
                "Check-in": a_data(p["check_in"]).strftime("%d/%m/%y"),
                "Check-out": a_data(p["check_out"]).strftime("%d/%m/%y"),
                "€/notte": euro(p["prezzo_notte"]),
                "Totale": euro(notti * float(p["prezzo_notte"])),
            })
        st.dataframe(pd.DataFrame(righe), hide_index=True)

        # Selezione prenotazione.
        opzioni = {
            f'{p["intestatario"]} · {p["hotel"]} N.{p["camera"]} · '
            f'{a_data(p["check_in"]).strftime("%d/%m/%y")}': p["id"]
            for p in prenotazioni
        }
        scelta = st.selectbox("Seleziona una prenotazione", list(opzioni.keys()), key="sel_pren")
        sel_id = opzioni[scelta]

        # Tasti Modifica ed Elimina affiancati.
        b1, b2 = st.columns(2)
        if b1.button("✏️  Modifica prenotazione selezionata"):
            st.session_state.edit_id = sel_id
            st.rerun()
        if b2.button("🗑️  Elimina prenotazione selezionata"):
            st.session_state.prenotazioni = [
                p for p in st.session_state.prenotazioni if p["id"] != sel_id
            ]
            salva_prenotazioni()
            _chiudi_modifica()
            st.success("Prenotazione eliminata.")
            st.rerun()
        if st.session_state.get("edit_id"):
            st.caption("Il modulo di modifica è in alto, sotto gli incassi. ⬆️")


def sezione_storico(giorno):
    """Storico incassi in TABELLE chiare (niente grafici, niente pagine multiple):
    incassi giornalieri (settimana selezionata), settimanali (lun–dom) e mensili,
    tutto agganciato alla settimana scelta in alto. Dentro un unico expander."""
    with st.expander("📊  Storico & statistiche incassi", expanded=False):
        if not st.session_state.prenotazioni:
            st.info("Ancora nessun dato storico: inserisci le prime prenotazioni.")
            return

        sett = giorni_settimana(giorno)
        lun, dom = sett[0], sett[-1]

        # 1) GIORNALIERI — i 7 giorni della settimana selezionata (lun–dom) + totale.
        st.markdown(
            f"**📅 Incassi giornalieri — settimana {lun.strftime('%d/%m')} → {dom.strftime('%d/%m/%Y')}**"
        )
        righe_g = [
            {"Giorno": f"{GIORNI_IT[d.weekday()]} {d.strftime('%d/%m')}",
             "Incasso": euro(incasso_intervallo(d, d + dt.timedelta(days=1)))}
            for d in sett
        ]
        righe_g.append({"Giorno": "TOTALE SETTIMANA",
                        "Incasso": euro(incasso_intervallo(lun, dom + dt.timedelta(days=1)))})
        st.table(pd.DataFrame(righe_g).set_index("Giorno"))

        # 2) SETTIMANALI — le ultime 8 settimane (lun–dom) fino a quella selezionata.
        st.markdown("**🗓️ Incassi settimanali (lun–dom)**")
        righe_s = []
        for k in range(7, -1, -1):
            l = lun - dt.timedelta(days=7 * k)
            dd = l + dt.timedelta(days=6)
            etich = f"{l.strftime('%d/%m')} → {dd.strftime('%d/%m/%y')}"
            if l == lun:
                etich += "  ⟵ selezionata"
            righe_s.append({"Settimana": etich,
                            "Incasso": euro(incasso_intervallo(l, dd + dt.timedelta(days=1)))})
        st.table(pd.DataFrame(righe_s).set_index("Settimana"))

        # 3) MENSILI — i 12 mesi dell'anno della settimana selezionata + totale.
        anno = giorno.year
        st.markdown(f"**📆 Incassi mensili — anno {anno}**")
        righe_m = [{"Mese": MESI_IT[m - 1], "Incasso": euro(incasso_mese(anno, m))}
                   for m in range(1, 13)]
        righe_m.append({"Mese": "TOTALE ANNO", "Incasso": euro(incasso_anno(anno))})
        st.table(pd.DataFrame(righe_m).set_index("Mese"))


def sezione_backup():
    """Esportazione/ripristino dei dati per non perdere mai lo storico."""
    with st.expander("💾  Backup / ripristino dati", expanded=False):
        df = pd.DataFrame(st.session_state.prenotazioni, columns=COLONNE)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️  Scarica backup CSV", csv,
            file_name=f"prenotazioni_backup_{dt.date.today().isoformat()}.csv",
            mime="text/csv",
        )
        st.caption(
            "Consiglio: scarica il backup ogni tanto. Su Streamlit Cloud il file può "
            "azzerarsi ai riavvii; con questo CSV ripristini tutto in un secondo."
        )
        up = st.file_uploader("Ripristina da un CSV di backup", type=["csv"])
        if up is not None and st.button("♻️  Ripristina (sostituisce i dati attuali)"):
            try:
                dfu = pd.read_csv(up, dtype=str).fillna("")
                recs = dfu.to_dict("records")
                for r in recs:
                    r["camera"] = int(float(r["camera"]))
                    r["prezzo_notte"] = float(r["prezzo_notte"])
                    r["prezzo_standard"] = float(r.get("prezzo_standard") or 0)
                    r["deroga"] = str(r.get("deroga")).lower() in ("true", "1", "vero")
                st.session_state.prenotazioni = recs
                salva_prenotazioni()
                st.success(f"Ripristinate {len(recs)} prenotazioni.")
                st.rerun()
            except Exception as e:
                st.error(f"File non valido: {e}")


# =============================================================================
# 9. AZIONI DA CLICK SULLE CELLE E SELETTORE GIORNO/SETTIMANA
# =============================================================================
def _reset_home():
    """Riporta l'app allo stato iniziale e RICARICA tutte le info da disco."""
    # Chiude eventuali moduli aperti (modifica/aggiunta) e pulisce i campi.
    _chiudi_modifica()
    for k in [
        "open_add", "add_ci", "add_co",
        "f_hotel", "f_camera", "f_uso", "f_deroga",
        "f_intestatario", "f_tel", "f_email", "f_note", "f_tipo_cliente",
        "sel_pren",
    ]:
        st.session_state.pop(k, None)
    # Torna alla settimana odierna.
    st.session_state["giorno_sel"] = max(dt.date(2026, 1, 1), dt.date.today())
    # Ricarica le prenotazioni dal file (dati sempre aggiornati).
    st.session_state.prenotazioni = carica_prenotazioni()


def gestisci_click_celle():
    """Legge i parametri URL prodotti dal click su una cella della griglia o dal
    tasto HOME e apre il modulo giusto / esegue il reset."""
    qp = st.query_params
    act = qp.get("act")
    if not act:
        return

    if act == "home":
        _reset_home()

    elif act == "add":
        h = qp.get("h")
        r = qp.get("r")
        d = qp.get("d")
        if h in HOTELS and r is not None:
            rooms = HOTELS[h]["rooms"]
            try:
                r_int = int(r)
            except (TypeError, ValueError):
                r_int = None
            if r_int in rooms:
                try:
                    d_obj = dt.date.fromisoformat(d)
                except (TypeError, ValueError):
                    d_obj = dt.date.today()
                _chiudi_modifica()  # eventuale modifica aperta viene chiusa
                st.session_state["f_hotel"] = h
                st.session_state["f_camera"] = r_int
                st.session_state["f_uso"] = USI_PER_TIPO[rooms[r_int]][0]
                st.session_state["f_deroga"] = False
                st.session_state["add_ci"] = d_obj
                st.session_state["add_co"] = d_obj + dt.timedelta(days=1)
                st.session_state["open_add"] = True

    elif act == "edit":
        bid = qp.get("id")
        if bid and any(p["id"] == bid for p in st.session_state.prenotazioni):
            st.session_state.pop("open_add", None)
            st.session_state.edit_id = bid

    # Pulisco l'URL dai parametri d'azione, ma CONSERVO il token di accesso
    # (auth) così non viene richiesta di nuovo la password.
    auth = qp.get("auth")
    st.query_params.clear()
    if auth:
        st.query_params["auth"] = auth


def _min_settimana():
    """Lunedì della prima settimana del 2026 (per permettere di mostrare la
    settimana che contiene il 1° gennaio)."""
    return inizio_settimana(dt.date(2026, 1, 1))


def _giorno_clamp(d):
    return max(_min_settimana(), inizio_settimana(d))


def _shift_settimana(delta):
    """Callback frecce: sposta di una settimana (eseguita prima del widget)."""
    st.session_state["giorno_sel"] = _giorno_clamp(
        st.session_state["giorno_sel"] + dt.timedelta(days=delta)
    )


def _vai_oggi():
    """Callback tasto Oggi: va alla settimana corrente (lunedì)."""
    st.session_state["giorno_sel"] = _giorno_clamp(dt.date.today())


def _snap_lunedi():
    """Callback calendario: qualsiasi giorno scelto viene riportato al LUNEDÌ
    della sua settimana, così il selettore rappresenta la settimana lun–dom."""
    st.session_state["giorno_sel"] = _giorno_clamp(st.session_state["giorno_sel"])


def selettore_giorno():
    """Selettore di SETTIMANA (lunedì–domenica): calendario che si aggancia al
    lunedì + frecce settimana precedente/successiva + tasto Oggi.
    Restituisce il lunedì della settimana scelta."""
    oggi = dt.date.today()
    default = oggi if oggi >= dt.date(2026, 1, 1) else dt.date(2026, 1, 1)
    if "giorno_sel" not in st.session_state:
        st.session_state["giorno_sel"] = _giorno_clamp(default)   # parte da lunedì

    st.markdown("##### 📅 Settimana da visualizzare (lun–dom)")
    cprev, cpick, cnext = st.columns([1, 3, 1])

    cprev.button("◀", help="Settimana precedente",
                 on_click=_shift_settimana, args=(-7,))
    cnext.button("▶", help="Settimana successiva",
                 on_click=_shift_settimana, args=(7,))

    # Il calendario mostra il lunedì; scegliendo un altro giorno si aggancia
    # automaticamente al lunedì della sua settimana (on_change).
    giorno = cpick.date_input(
        "Settimana", min_value=_min_settimana(),
        format="DD/MM/YYYY", key="giorno_sel", label_visibility="collapsed",
        on_change=_snap_lunedi,
    )
    giorno = inizio_settimana(giorno)   # sicurezza: sempre lunedì

    lun_oggi = inizio_settimana(oggi)
    if oggi >= dt.date(2026, 1, 1) and giorno != lun_oggi:
        st.button("📍  Questa settimana", on_click=_vai_oggi)

    sett = giorni_settimana(giorno)
    st.caption(
        f"Settimana: **Lun {sett[0].strftime('%d/%m/%Y')} → Dom "
        f"{sett[-1].strftime('%d/%m/%Y')}**"
    )
    return giorno


def password_configurata():
    """Restituisce la password corretta letta dai Secrets di Streamlit (chiave
    "password") o dalla variabile d'ambiente APP_PASSWORD. None se non impostata.
    In questo modo la password NON è scritta nel codice."""
    try:
        pwd = st.secrets.get("password")
        if pwd:
            return str(pwd)
    except Exception:
        pass
    return os.environ.get("APP_PASSWORD")


def _token(pwd):
    """Token (non reversibile) derivato dalla password: viene messo nell'URL per
    mantenere l'accesso attraverso i ricaricamenti di pagina e i riavvii dei
    server di Streamlit, senza esporre la password."""
    return hashlib.sha256(("caciorgna::" + str(pwd)).encode()).hexdigest()[:20]


def _auth_qs():
    """Frammento '&auth=TOKEN' da accodare ai link, per non perdere l'accesso
    quando il click ricarica la pagina. Vuoto se non autenticato."""
    tok = st.session_state.get("auth_token")
    return f"&auth={tok}" if tok else ""


def autenticazione():
    """Mostra la schermata di login se l'utente non è autenticato.
    Ritorna True se autenticato, False altrimenti.

    L'accesso viene ricordato tramite un token nell'URL: così la password è
    chiesta solo all'inizio (non ad ogni prenotazione) e l'app non si blocca
    quando Streamlit ricarica/riavvia. Viene richiesta di nuovo solo quando si
    esce davvero dall'app (URL senza token) o dopo il Logout."""
    pwd_corretta = password_configurata()

    # Già autenticato in questa sessione.
    if st.session_state.get("autenticato", False):
        if pwd_corretta is not None and not st.session_state.get("auth_token"):
            st.session_state.auth_token = _token(pwd_corretta)
        return True

    # Auto-login dal token presente nell'URL (sopravvive a reload e riavvii).
    if pwd_corretta is not None:
        tok_url = st.query_params.get("auth")
        if tok_url and tok_url == _token(pwd_corretta):
            st.session_state.autenticato = True
            st.session_state.auth_token = tok_url
            return True

    # Prima dell'accesso si vede SOLO questa schermata di login.
    sezione_testata()
    st.markdown("#### 🔒 Accesso riservato")
    with st.form("login_form"):
        pwd = st.text_input(
            "Password", type="password", placeholder="Inserisci la password"
        )
        accedi = st.form_submit_button("Accedi")
    if accedi:
        if pwd_corretta is None:
            st.error(
                "Password non configurata. Imposta il Secret 'password' su "
                "Streamlit Cloud (o la variabile d'ambiente APP_PASSWORD in locale)."
            )
        elif pwd == pwd_corretta:
            st.session_state.autenticato = True
            st.session_state.auth_token = _token(pwd_corretta)
            st.query_params["auth"] = st.session_state.auth_token
            st.rerun()
        else:
            st.error("Password errata. Riprova.")
    return False


# =============================================================================
# 11. MAIN
# =============================================================================
def main():
    inietta_css()
    init_stato()

    # --- LOGIN: tutto il resto è visibile solo dopo l'accesso ---
    if not autenticazione():
        return

    # --- Sidebar: tasto Logout (chiede di nuovo la password) ---
    with st.sidebar:
        st.markdown("**Caciorgna Hotels**")
        if st.button("🚪  Logout"):
            st.session_state.autenticato = False
            st.session_state.pop("auth_token", None)
            st.query_params.clear()
            st.rerun()

    gestisci_click_celle()      # interpreta i click sulle celle e il tasto HOME
    # Tasto HOME fisso, sempre visibile: torna all'inizio e ricarica i dati.
    st.markdown(
        f'<a class="home-fab" target="_self" href="?act=home{_auth_qs()}" '
        'title="Torna alla pagina iniziale e aggiorna">🏠 Home</a>',
        unsafe_allow_html=True,
    )
    sezione_testata()

    # --- Selettore giorno/settimana (calendario + frecce + Oggi) ---
    giorno = selettore_giorno()

    # --- KPI incassi sempre in vista in cima ---
    sezione_kpi(giorno)

    # --- Modulo di modifica (compare in alto cliccando una cella rossa) ---
    sezione_modifica()

    # --- Form di inserimento prenotazione (si apre cliccando una cella verde) ---
    sezione_form_prenotazione(giorno)

    # --- Storico & statistiche (collassato, non appesantisce la pagina) ---
    sezione_storico(giorno)

    # --- Griglie settimanali per le tre strutture ---
    sezione_griglie(giorno)

    # --- Gestione: modifica / elimina prenotazioni ---
    sezione_gestione()

    # --- Backup / ripristino dati ---
    sezione_backup()

    st.caption(
        "Suggerimento: tocca una cella **verde** per prenotare o una **rossa** per "
        "modificare. Dati in data/prenotazioni.csv; su Streamlit Cloud scarica il "
        "backup CSV per conservare lo storico (vedi README)."
    )


if __name__ == "__main__":
    main()
