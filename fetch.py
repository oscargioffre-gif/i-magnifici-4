#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch.py — SuperEnalotto  ➜  data.json
================================================================================
Aggiorna TUTTE le estrazioni con precisione ingegneristica, preservando l'intero
storico. Progettato per girare su GitHub Actions una volta al giorno di estrazione,
un'ora dopo il sorteggio (21:00 ora italiana).

Principi di progetto
--------------------
1.  FONTE DI VERITÀ UNICA. Scrive solo i fatti oggettivi dell'estrazione
    (data, sestina, jolly, superstar). Il calcolo delle vincite dei "Magnifici 4"
    resta interamente nel frontend (index.html), che ricalcola se `wins` è assente.
2.  STORICO INDISTRUTTIBILE. Non parte mai da zero: carica il data.json esistente,
    vi fonde le estrazioni appena lette (che hanno la precedenza in caso di
    correzione), e riscrive l'intero archivio ordinato dal più recente.
    Il merge può solo AGGIUNGERE o CORREGGERE: non cancella mai nulla.
3.  FAIL-SAFE. Se la fonte è irraggiungibile o il parsing non produce risultati
    validi, il data.json esistente viene lasciato intatto e lo script esce con 0
    (nessun commit distruttivo).
4.  PARSING ANTI-SHIFT. La sestina è ancorata all'etichetta "Jolly": si prendono
    i 6 numeri validi IMMEDIATAMENTE PRECEDENTI. Questo scarta automaticamente
    numeri spuri (numero di concorso, cifre della data) che in passato facevano
    "scorrere" i valori (sestina→jolly→superstar). Validazione rigorosa a valle.
"""

import json
import re
import sys
from datetime import datetime, timezone, date as date_cls
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Dipendenze mancanti. Esegui: pip install requests beautifulsoup4 lxml")
    sys.exit(1)

# ─── CONFIGURAZIONE ───────────────────────────────────────────────────────────
DATA_FILE = Path("data.json")

# Fonti in ordine di priorità: l'archivio ufficiale .it è fresco e completo,
# la home come rete di sicurezza per l'ultimissima estrazione.
SOURCES = [
    "https://www.superenalotto.it/archivio-estrazioni",
    "https://www.superenalotto.it/",
]

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}

MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}
MESI_NOME = {v: k.capitalize() for k, v in MESI.items()}
GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]

# "4 luglio 2026", eventualmente preceduto dal giorno della settimana (ignorato).
DATE_RX = re.compile(
    r"(\d{1,2})\s+("
    r"gennaio|febbraio|marzo|aprile|maggio|giugno|"
    r"luglio|agosto|settembre|ottobre|novembre|dicembre)\s+(\d{4})",
    re.IGNORECASE,
)
# Token: o un'etichetta (jolly / superstar) o un numero di 1-3 cifre.
TOKEN_RX = re.compile(r"(?P<lab>jolly|superstar|super\s*star)|(?P<num>\d{1,3})", re.IGNORECASE)


def log(msg: str) -> None:
    print(msg, flush=True)


# ─── RETE ─────────────────────────────────────────────────────────────────────
def fetch_html(url: str) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        r.raise_for_status()
        log(f"  OK  {url}  ({len(r.text):,} char)")
        return r.text
    except Exception as e:  # noqa: BLE001 — vogliamo degradare, non crashare
        log(f"  FAIL {url}: {e}")
        return ""


# ─── PARSING ──────────────────────────────────────────────────────────────────
def date_string(y: int, m: int, d: int) -> str:
    """Costruisce la stringa data nel formato atteso dal frontend."""
    wd = date_cls(y, m, d).weekday()          # 0 = Lunedì
    return f"{GIORNI[wd]} {d} {MESI_NOME[m]} {y}"


def _parse_block(body: str):
    """
    Estrae (sestina, jolly, superstar) da un blocco di testo di UNA estrazione.
    Ritorna None se il blocco non contiene un'estrazione valida.
    """
    seq = []  # sequenza ordinata di ('num', v) e ('lab', 'jolly'|'superstar')
    for mo in TOKEN_RX.finditer(body):
        if mo.group("lab"):
            lab = "superstar" if "super" in mo.group("lab").lower() else "jolly"
            seq.append(("lab", lab))
        else:
            seq.append(("num", int(mo.group("num"))))

    valid = [v for k, v in seq if k == "num" and 1 <= v <= 90]
    has_jolly = any(k == "lab" and v == "jolly" for k, v in seq)

    def num_between(label: str):
        """Primo numero valido DOPO `label` e PRIMA dell'etichetta successiva."""
        seen = False
        for k, v in seq:
            if k == "lab":
                if v == label and not seen:
                    seen = True
                elif seen:
                    break            # raggiunta l'etichetta seguente: stop, niente sconfinamento
            elif seen and k == "num" and 1 <= v <= 90:
                return v
        return None

    sestina = jolly = superstar = None

    # Metodo A — ancorato alle etichette (robusto contro numeri spuri).
    if has_jolly:
        before = []
        for k, v in seq:
            if k == "lab" and v == "jolly":
                break
            if k == "num" and 1 <= v <= 90:
                before.append(v)
        cand_sestina = before[-6:]            # i 6 IMMEDIATAMENTE prima del Jolly
        cand_jolly = num_between("jolly")
        cand_ss = num_between("superstar")
        if len(cand_sestina) == 6 and len(set(cand_sestina)) == 6 and cand_jolly and cand_ss:
            sestina, jolly, superstar = cand_sestina, cand_jolly, cand_ss

    # Metodo B — posizionale (fallback se le etichette non ci sono).
    if sestina is None and len(valid) >= 8:
        cand_sestina = valid[0:6]
        if len(set(cand_sestina)) == 6:
            sestina, jolly, superstar = cand_sestina, valid[6], valid[7]

    if sestina is None:
        return None
    if not (1 <= jolly <= 90 and 1 <= superstar <= 90):
        return None
    return sestina, jolly, superstar


def parse_draws(html: str):
    """Ritorna una lista di dict {key,(y,m,d),date,numbers,jolly,superstar}."""
    if not html:
        return []
    text = BeautifulSoup(html, "html.parser").get_text(separator=" ")
    text = re.sub(r"\s+", " ", text)

    matches = list(DATE_RX.finditer(text))
    draws = []
    seen_keys = set()

    for i, m in enumerate(matches):
        d, mese_it, y = int(m.group(1)), m.group(2).lower(), int(m.group(3))
        mese_n = MESI[mese_it]
        # Sanity sulla data (scarta refusi tipo "31 febbraio 2026").
        try:
            date_cls(y, mese_n, d)
        except ValueError:
            continue

        key = (y, mese_n, d)
        if key in seen_keys:
            continue

        # Il corpo dell'estrazione va da SUBITO DOPO questa data fino alla prossima.
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        parsed = _parse_block(text[start:end])
        if not parsed:
            continue

        sestina, jolly, superstar = parsed
        seen_keys.add(key)
        draws.append({
            "key": key,
            "date": date_string(y, mese_n, d),
            "numbers": sestina,
            "jolly": jolly,
            "superstar": superstar,
        })
        log(f"  ✓ {date_string(y, mese_n, d)}: {sestina}  J:{jolly}  SS:{superstar}")

    return draws


# ─── ARCHIVIO / MERGE ─────────────────────────────────────────────────────────
def _key_from_date_str(date_str: str):
    m = DATE_RX.search(date_str or "")
    if not m:
        return None
    d, mese_it, y = int(m.group(1)), m.group(2).lower(), int(m.group(3))
    try:
        date_cls(y, MESI[mese_it], d)
    except ValueError:
        return None
    return (y, MESI[mese_it], d)


def load_existing():
    """Carica l'archivio esistente come dict {key: draw-pulito}."""
    if not DATA_FILE.exists():
        return {}
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        log(f"  data.json illeggibile ({e}) — riparto dallo scraping.")
        return {}

    out = {}
    for draw in data.get("draws", []):
        key = _key_from_date_str(draw.get("date", ""))
        nums = draw.get("numbers")
        if not key or not isinstance(nums, list) or len(nums) != 6:
            continue
        out[key] = {
            "date": draw["date"],
            "numbers": [int(n) for n in nums],
            "jolly": int(draw["jolly"]),
            "superstar": int(draw["superstar"]),
        }
    return out


def main() -> int:
    log("── Aggiornamento SuperEnalotto ──────────────────────────────")

    archive = load_existing()
    log(f"Archivio esistente: {len(archive)} estrazioni.")

    scraped = []
    for url in SOURCES:
        html = fetch_html(url)
        found = parse_draws(html)
        scraped.extend(found)
        # L'archivio (prima fonte) di norma basta; la home è solo rete di sicurezza.
        if url.endswith("archivio-estrazioni") and len(found) >= 10:
            break

    if not scraped:
        log("Nessuna estrazione valida dallo scraping — archivio lasciato intatto.")
        return 0

    # MERGE: lo scraping ha la precedenza (corregge eventuali errori storici),
    # ma non cancella mai le estrazioni già presenti e non più online.
    added, updated = 0, 0
    for dr in scraped:
        key = dr["key"]
        clean = {k: dr[k] for k in ("date", "numbers", "jolly", "superstar")}
        if key not in archive:
            added += 1
        elif archive[key] != clean:
            updated += 1
        archive[key] = clean

    # Ordina dal più recente al più vecchio (per DATA reale, non stringa).
    ordered = [archive[k] for k in sorted(archive.keys(), reverse=True)]

    payload = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "draws": ordered,
    }
    new_json = json.dumps(payload, ensure_ascii=False, indent=2)

    # Evita commit inutili: scrivi solo se il contenuto è cambiato.
    old_json = DATA_FILE.read_text(encoding="utf-8") if DATA_FILE.exists() else ""

    def strip_updated(s: str) -> str:
        return re.sub(r'"updated":\s*"[^"]*",\s*', "", s)

    if strip_updated(old_json) == strip_updated(new_json):
        log(f"Nessuna variazione (aggiunte 0, corrette 0). Totale {len(ordered)}. Nessun commit.")
        return 0

    DATA_FILE.write_text(new_json, encoding="utf-8")
    log(f"Scritto data.json — aggiunte {added}, corrette {updated}, totale {len(ordered)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
