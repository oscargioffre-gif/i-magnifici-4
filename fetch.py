import requests, re, json, sys
from datetime import datetime, date as dt_date
from bs4 import BeautifulSoup

MESI_EN_IT = {
    'January':'Gennaio','February':'Febbraio','March':'Marzo','April':'Aprile',
    'May':'Maggio','June':'Giugno','July':'Luglio','August':'Agosto',
    'September':'Settembre','October':'Ottobre','November':'Novembre','December':'Dicembre'
}
MESI_IT_N = {
    'Gennaio':1,'Febbraio':2,'Marzo':3,'Aprile':4,'Maggio':5,'Giugno':6,
    'Luglio':7,'Agosto':8,'Settembre':9,'Ottobre':10,'Novembre':11,'Dicembre':12
}
GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato','Domenica']

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

URL = 'https://www.superenalotto.com/en/results'

def get_html(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        r.raise_for_status()
        print(f'OK: {url} ({len(r.text)} chars)')
        return r.text
    except Exception as e:
        print(f'FAIL {url}: {e}')
        return ''

html = get_html(URL)

if not html:
    print('Sito non raggiungibile - mantengo data.json')
    sys.exit(0)

soup = BeautifulSoup(html, 'html.parser')

# Regex per la data nel formato "7 March 2026"
date_rx = re.compile(
    r'(\d{1,2})\s+'
    r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+'
    r'(\d{4})',
    re.IGNORECASE
)

# Regex per il jackpot
jp_rx = re.compile(r'([\d.]+)\s*€')

results = []

# Ogni estrazione è in un <table>
# La struttura ha: riga di date, riga con 8 celle numeriche
#   (6 estratti + Jolly + SuperStar), riga con etichette "Jolly" / "SuperStar"
for table in soup.find_all('table'):
    text = table.get_text(separator=' ', strip=True)
    dm = date_rx.search(text)
    if not dm:
        continue

    d = int(dm.group(1))
    m_en = dm.group(2).capitalize()
    y = int(dm.group(3))
    m_it = MESI_EN_IT.get(m_en, m_en)
    m_n = MESI_IT_N.get(m_it, 1)

    # Trova TUTTE le celle <td> nella tabella
    tds = table.find_all('td')

    # Estrai solo le celle che contengono esattamente un numero 1-90
    # e che NON contengono testo aggiuntivo come "Jolly", "SuperStar", date, "€"
    raw_nums = []
    for td in tds:
        cell_text = td.get_text(strip=True)
        # Cella con un solo numero puro (1-90)
        if re.fullmatch(r'\d{1,2}', cell_text):
            val = int(cell_text)
            if 1 <= val <= 90:
                raw_nums.append(val)

    # La pagina ha esattamente 8 numeri per estrazione:
    # 6 estratti + 1 Jolly + 1 SuperStar
    if len(raw_nums) < 8:
        print(f'  SKIP {d} {m_it} {y}: trovati solo {len(raw_nums)} numeri: {raw_nums}')
        continue

    six = raw_nums[0:6]
    jolly = raw_nums[6]
    superstar = raw_nums[7]

    # Validazione: i 6 numeri estratti devono essere tutti diversi
    if len(set(six)) != 6:
        print(f'  SKIP {d} {m_it} {y}: numeri duplicati nella sestina {six}')
        continue

    # Validazione: Jolly non deve essere tra i 6 estratti
    if jolly in six:
        print(f'  WARN {d} {m_it} {y}: Jolly {jolly} presente nella sestina {six}')

    try:
        wd = dt_date(y, m_n, d).weekday()
        date_str = f'{GIORNI[wd]} {d} {m_it} {y}'
    except ValueError:
        date_str = f'{d} {m_it} {y}'

    # Cerca jackpot
    jp_match = jp_rx.search(text)
    jp = jp_match.group(0).strip() if jp_match else None

    # Evita duplicati
    if not any(r['numbers'] == six for r in results):
        results.append({
            'date': date_str,
            'numbers': six,
            'jolly': jolly,
            'superstar': superstar,
            'jackpot': jp,
        })
        print(f'  OK {date_str}: {six}  J:{jolly}  SS:{superstar}  JP:{jp}')

print(f'\nTrovate {len(results)} estrazioni')

if not results:
    print('Nessun risultato trovato - mantengo data.json esistente')
    sys.exit(0)

with open('data.json', 'w', encoding='utf-8') as f:
    json.dump(
        {
            'updated': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
            'draws': results,
        },
        f,
        ensure_ascii=False,
        indent=2,
    )

print(f'Salvate {len(results)} estrazioni in data.json')
