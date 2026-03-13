import requests, re, json, sys
from datetime import datetime, date as dt_date
from bs4 import BeautifulSoup

MESI_IT = {
    'Gennaio':1,'Febbraio':2,'Marzo':3,'Aprile':4,'Maggio':5,'Giugno':6,
    'Luglio':7,'Agosto':8,'Settembre':9,'Ottobre':10,'Novembre':11,'Dicembre':12
}
GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato','Domenica']

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'it-IT,it;q=0.9',
}

URL = 'https://www.superenalotto.it/archivio-estrazioni'

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

date_rx = re.compile(r'(\d{1,2})\s+(Gennaio|Febbraio|Marzo|Aprile|Maggio|Giugno|Luglio|Agosto|Settembre|Ottobre|Novembre|Dicembre)\s+(\d{4})')

results = []

for tr in soup.find_all('tr'):
    tds = tr.find_all('td')
    if len(tds) < 4:
        continue

    cell_concorso = tds[0].get_text(separator=' ', strip=True)
    dm = date_rx.search(cell_concorso)
    if not dm:
        continue

    d = int(dm.group(1))
    m_it = dm.group(2)
    y = int(dm.group(3))
    m_n = MESI_IT[m_it]

    cell_nums = tds[1].get_text(separator=' ', strip=True)
    nums = [int(x) for x in re.findall(r'\d+', cell_nums)]
    if len(nums) != 6:
        print(f'  SKIP {d} {m_it} {y}: numeri={nums}')
        continue

    jolly_text = tds[2].get_text(strip=True)
    jolly = int(re.search(r'\d+', jolly_text).group())

    ss_text = tds[3].get_text(strip=True)
    ss = int(re.search(r'\d+', ss_text).group())

    try:
        wd = dt_date(y, m_n, d).weekday()
        date_str = f'{GIORNI[wd]} {d} {m_it} {y}'
    except ValueError:
        date_str = f'{d} {m_it} {y}'

    if not any(r['numbers'] == nums for r in results):
        results.append({
            'date': date_str,
            'numbers': nums,
            'jolly': jolly,
            'superstar': ss,
        })
        print(f'  OK {date_str}: {nums}  J:{jolly}  SS:{ss}')

    if len(results) >= 10:
        break

print(f'\nTrovate {len(results)} estrazioni')

if not results:
    print('Nessun risultato - mantengo data.json')
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
