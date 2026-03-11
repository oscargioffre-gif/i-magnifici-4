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

def get_html(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        r.raise_for_status()
        print(f'OK: {url} ({len(r.text)} chars)')
        return r.text
    except Exception as e:
        print(f'FAIL {url}: {e}')
        return ''

html = get_html('https://www.superenalotto.com/en/results')

if not html:
    print('Sito non raggiungibile - mantengo data.json')
    sys.exit(0)

soup = BeautifulSoup(html, 'lxml')

results = []
date_rx = re.compile(r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', re.IGNORECASE)
num_rx  = re.compile(r'\b([1-9]|[1-8][0-9]|90)\b')

# Trova tutte le tabelle con i risultati
for table in soup.find_all('table'):
    text = table.get_text(separator=' ')
    dm = date_rx.search(text)
    if not dm:
        continue
    d = int(dm.group(1))
    m_en = dm.group(2).capitalize()
    y = int(dm.group(3))
    m_it = MESI_EN_IT.get(m_en, m_en)
    m_n  = MESI_IT_N.get(m_it, 1)

    nums = list(dict.fromkeys(int(x) for x in num_rx.findall(text) if 1 <= int(x) <= 90))
    if len(nums) < 8:
        continue
    six, jolly, ss = nums[:6], nums[6], nums[7]
    if len(set(six)) != 6:
        continue

    try:
        wd = dt_date(y, m_n, d).weekday()
        date_str = f'{GIORNI[wd]} {d} {m_it} {y}'
    except:
        date_str = f'{d} {m_it} {y}'

    jp_m = re.search(r'([\d\.]+\.[\d]{3}(?:\.[\d]{3})?)\s*€', text)
    jp = jp_m.group(0).strip() if jp_m else None

    if not any(r['numbers'] == six for r in results):
        results.append({'date':date_str,'numbers':six,'jolly':jolly,'superstar':ss,'jackpot':jp})
        print(f'  ✓ {date_str}: {six} J:{jolly} SS:{ss}')

    if len(results) >= 4:
        break

if not results:
    print('Nessun risultato - mantengo data.json')
    sys.exit(0)

with open('data.json','w',encoding='utf-8') as f:
    json.dump({'updated':datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),'draws':results}, f, ensure_ascii=False, indent=2)
print(f'Salvate {len(results)} estrazioni ✅')
