import requests, re, json, sys
from datetime import datetime, date as dt_date

MESI = {
    'gennaio':1,'febbraio':2,'marzo':3,'aprile':4,
    'maggio':5,'giugno':6,'luglio':7,'agosto':8,
    'settembre':9,'ottobre':10,'novembre':11,'dicembre':12
}
MESI_IT = {v:k.capitalize() for k,v in MESI.items()}
GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato','Domenica']

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'it-IT,it;q=0.9',
    'Referer': 'https://www.google.it/',
}

html = ''
for url in ['https://www.superenalotto.com/risultati', 'https://www.superenalotto.net/risultati']:
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        r.raise_for_status()
        if len(r.text) > 5000:
            html = r.text
            print(f'OK: {url} ({len(html)} chars)')
            break
    except Exception as e:
        print(f'FAIL {url}: {e}')

if not html:
    print('Nessun sito raggiungibile — mantengo data.json')
    sys.exit(0)

from bs4 import BeautifulSoup
soup = BeautifulSoup(html, 'lxml')
for tag in soup(['script','style','noscript']):
    tag.decompose()
text = soup.get_text(separator='\n')

date_rx = re.compile(r'(\d{1,2})\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+(\d{4})', re.IGNORECASE)
num_rx = re.compile(r'\b([1-9]|[1-8][0-9]|90)\b')

results = []
lines = text.split('\n')
i = 0
while i < len(lines) and len(results) < 4:
    dm = date_rx.search(lines[i])
    if dm:
        d, m_str, y = int(dm.group(1)), dm.group(2).lower(), int(dm.group(3))
        block = '\n'.join(lines[i:i+25])
        nums = list(dict.fromkeys(int(x) for x in num_rx.findall(block) if 1 <= int(x) <= 90))
        if len(nums) >= 8:
            six, jolly, ss = nums[:6], nums[6], nums[7]
            if len(set(six)) == 6:
                jp_m = re.search(r'([\d\.]+\.000)\s*€?', block)
                jp = (jp_m.group(0).strip() + (' €' if jp_m and '€' not in jp_m.group(0) else '')) if jp_m else None
                mese_n = MESI.get(m_str, 1)
                date_str = f'{d} {MESI_IT[mese_n]} {y}'
                try:
                    wd = dt_date(y, mese_n, d).weekday()
                    date_str = f'{GIORNI[wd]} {d} {MESI_IT[mese_n]} {y}'
                except:
                    pass
                if not any(r['numbers'] == six for r in results):
                    results.append({'date':date_str,'numbers':six,'jolly':jolly,'superstar':ss,'jackpot':jp})
                    print(f'  {date_str}: {six} J:{jolly} SS:{ss}')
    i += 1

if not results:
    print('Parser non ha trovato risultati — mantengo data.json')
    sys.exit(0)

with open('data.json','w',encoding='utf-8') as f:
    json.dump({'updated':datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),'draws':results}, f, ensure_ascii=False, indent=2)
print(f'Salvate {len(results)} estrazioni')
