# -*- coding: utf-8 -*-
"""
Fetch estrazioni SuperEnalotto — multi-fonte con fallback in cascata.
Fonti (in ordine): superenalotto.net -> lottologia.com ->
                   estrazionedellotto.it -> superenalotto.com
Ogni risultato viene validato (6 numeri unici 1-90 + jolly + superstar)
e fuso con data.json esistente senza duplicati.
"""
import requests, re, json, sys, itertools
from datetime import datetime, date as dt_date

MESI_EN = {'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,
           'july':7,'august':8,'september':9,'october':10,'november':11,'december':12}
MESI_ITN = {'gennaio':1,'febbraio':2,'marzo':3,'aprile':4,'maggio':5,'giugno':6,
            'luglio':7,'agosto':8,'settembre':9,'ottobre':10,'novembre':11,'dicembre':12}
MESI_IT = {1:'Gennaio',2:'Febbraio',3:'Marzo',4:'Aprile',5:'Maggio',6:'Giugno',
           7:'Luglio',8:'Agosto',9:'Settembre',10:'Ottobre',11:'Novembre',12:'Dicembre'}
GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato','Domenica']
OUR = [3,7,12,22,25,26,46,79]
COMBOS = list(itertools.combinations(OUR,6))

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,*/*;q=0.8',
    'Accept-Language': 'it-IT,it;q=0.9,en;q=0.8',
    'Cache-Control': 'no-cache',
}

def calc_wins(nums):
    w = {2:0,3:0,4:0,5:0,6:0}
    s = set(nums)
    for c in COMBOS:
        h = len(s & set(c))
        if h >= 2: w[h] += 1
    return w

def make_entry(y, m, d, six, jolly, ss):
    """Costruisce e valida una entry. Ritorna None se invalida."""
    if len(six) != 6 or len(set(six)) != 6: return None
    if not all(1 <= n <= 90 for n in six + [jolly, ss]): return None
    try:
        dd = dt_date(y, m, d)
    except ValueError:
        return None
    if dd > dt_date.today(): return None          # data futura = parse errato
    if dd.year < 2025: return None                # troppo vecchia
    six = sorted(six)
    date_it = f"{GIORNI[dd.weekday()]} {d} {MESI_IT[m]} {y}"
    return {'date': date_it, 'iso': dd.isoformat(), 'numbers': six,
            'jolly': jolly, 'superstar': ss,
            'our_hits': len(set(OUR) & set(six)), 'wins': calc_wins(six)}

def get(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        r.raise_for_status()
        print(f'  OK  {url} ({len(r.text)} chars)')
        return r.text
    except Exception as e:
        print(f'  FAIL {url}: {e}')
        return ''

def parse_text_blocks(text, date_rx, month_map):
    """Parser generico: trova data, poi 8 numeri validi nelle righe seguenti."""
    out = []
    lines = text.split('\n')
    num_rx = re.compile(r'\b([1-9][0-9]?|90)\b')
    for i, line in enumerate(lines):
        dm = date_rx.search(line)
        if not dm: continue
        d = int(dm.group('d')); m = month_map.get(dm.group('m').lower()); y = int(dm.group('y'))
        if not m: continue
        block = '\n'.join(lines[i:i+15])
        # rimuovi la data dal blocco per non catturare giorno/anno come numeri
        block = date_rx.sub(' ', block)
        nums = []
        for x in num_rx.findall(block):
            v = int(x)
            if 1 <= v <= 90 and v not in nums:
                nums.append(v)
            if len(nums) == 8: break
        if len(nums) == 8:
            e = make_entry(y, m, d, nums[:6], nums[6], nums[7])
            if e and not any(r['iso'] == e['iso'] for r in out):
                out.append(e)
    return out

# ── FONTE 1: superenalotto.net (inglese, scrape-friendly) ─────────────────
def src_superenalotto_net():
    html = get('https://www.superenalotto.net/en/results')
    if not html: return []
    text = re.sub(r'<[^>]+>', '\n', html)
    rx = re.compile(r'(?:\w+\s+)?(?P<d>\d{1,2})(?:st|nd|rd|th)?\s+(?P<m>January|February|March|April|May|June|July|August|September|October|November|December)\s+(?P<y>\d{4})', re.I)
    return parse_text_blocks(text, rx, MESI_EN)

# ── FONTE 2: lottologia.com ───────────────────────────────────────────────
def src_lottologia():
    html = get('https://www.lottologia.com/superenalotto/?as=archivio-estrazioni')
    if not html: return []
    text = re.sub(r'<[^>]+>', '\n', html)
    rx = re.compile(r'(?P<d>\d{1,2})[\s/\-](?P<m>\d{2}|gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)[\s/\-](?P<y>\d{4})', re.I)
    mm = dict(MESI_ITN); mm.update({f'{i:02d}': i for i in range(1,13)})
    return parse_text_blocks(text, rx, mm)

# ── FONTE 3: estrazionedellotto.it ────────────────────────────────────────
def src_estrazionedellotto():
    html = get('https://www.estrazionedellotto.it/ultime-estrazioni-superenalotto')
    if not html: return []
    text = re.sub(r'<[^>]+>', '\n', html)
    rx = re.compile(r'(?P<d>\d{1,2})\s+(?P<m>gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+(?P<y>\d{4})', re.I)
    return parse_text_blocks(text, rx, MESI_ITN)

# ── FONTE 4: superenalotto.com (spesso 403, ultimo tentativo) ─────────────
def src_superenalotto_com():
    html = get('https://www.superenalotto.com/en/results/2026')
    if not html: return []
    text = re.sub(r'<[^>]+>', '\n', html)
    rx = re.compile(r'(?P<d>\d{1,2})\s+(?P<m>January|February|March|April|May|June|July|August|September|October|November|December)\s+(?P<y>\d{4})', re.I)
    return parse_text_blocks(text, rx, MESI_EN)

# ── MAIN ──────────────────────────────────────────────────────────────────
def main():
    existing = []
    try:
        existing = json.load(open('data.json'))['draws']
        print(f'data.json esistente: {len(existing)} estrazioni')
    except Exception:
        pass
    # indicizza per sestina (chiave robusta anche senza campo iso)
    by_key = {tuple(sorted(d['numbers'])): d for d in existing}

    sources = [('superenalotto.net', src_superenalotto_net),
               ('lottologia.com', src_lottologia),
               ('estrazionedellotto.it', src_estrazionedellotto),
               ('superenalotto.com', src_superenalotto_com)]

    fresh = []
    for name, fn in sources:
        print(f'Fonte: {name}')
        try:
            fresh = fn()
        except Exception as e:
            print(f'  ERRORE parser {name}: {e}')
            fresh = []
        if len(fresh) >= 1:
            print(f'  -> {len(fresh)} estrazioni valide')
            break

    if not fresh:
        print('::warning::Nessuna fonte raggiungibile — data.json NON aggiornato')
        sys.exit(0)   # non fallire: mantieni i dati esistenti

    nuovi = 0
    for e in fresh:
        k = tuple(e['numbers'])
        if k not in by_key:
            nuovi += 1
        by_key[k] = e   # aggiorna comunque (jolly/ss piu' precisi)

    merged = list(by_key.values())
    # ordina per data ISO quando disponibile, altrimenti mantieni ordine
    def sort_key(d):
        return d.get('iso', '0000-00-00')
    merged.sort(key=sort_key, reverse=True)
    merged = merged[:150]

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump({'updated': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
                   'draws': merged}, f, ensure_ascii=False, indent=2)
    print(f'Salvate {len(merged)} estrazioni ({nuovi} nuove)')

if __name__ == '__main__':
    main()
