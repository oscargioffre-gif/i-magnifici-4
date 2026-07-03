import requests, re, json, sys, itertools
from datetime import datetime, date as dt_date
from bs4 import BeautifulSoup

MESI_EN={'January':1,'February':2,'March':3,'April':4,'May':5,'June':6,
         'July':7,'August':8,'September':9,'October':10,'November':11,'December':12}
MESI_IT={1:'Gennaio',2:'Febbraio',3:'Marzo',4:'Aprile',5:'Maggio',6:'Giugno',
         7:'Luglio',8:'Agosto',9:'Settembre',10:'Ottobre',11:'Novembre',12:'Dicembre'}
GIORNI=['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato','Domenica']
OUR=[3,7,12,22,25,26,46,79]
COMBOS=list(itertools.combinations(OUR,6))

def calc_wins(nums):
    w={2:0,3:0,4:0,5:0,6:0}
    for c in COMBOS:
        h=len(set(c)&set(nums))
        if h>=2: w[h]+=1
    return w

HEADERS={
    'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36',
    'Accept':'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
    'Accept-Language':'en-US,en;q=0.9',
}

def fetch(url):
    try:
        r=requests.get(url,headers=HEADERS,timeout=25)
        r.raise_for_status()
        print(f'OK {url}: {len(r.text)} chars')
        return r.text
    except Exception as e:
        print(f'FAIL {url}: {e}')
        return ''

# Carica data.json esistente
existing=[]
try:
    existing=json.load(open('data.json'))['draws']
    existing_dates={d['date'] for d in existing}
    print(f'data.json esistente: {len(existing)} estrazioni')
except: existing_dates=set()

# Scarica archivio completo 2026
html=fetch('https://www.superenalotto.com/en/results/2026')
if not html:
    html=fetch('https://www.superenalotto.com/en/archive/draw-2026')

if not html:
    print('Nessun sito raggiungibile')
    sys.exit(0)

soup=BeautifulSoup(html,'lxml')
for t in soup(['script','style','noscript']): t.decompose()
text=soup.get_text(separator='\n')

date_rx=re.compile(r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',re.IGNORECASE)
num_rx=re.compile(r'\b([1-9]|[1-8][0-9]|90)\b')

results=[]
lines=text.split('\n')
i=0
while i<len(lines):
    dm=date_rx.search(lines[i])
    if dm:
        d2,m2,y2=int(dm.group(1)),dm.group(2).capitalize(),int(dm.group(3))
        mn=MESI_EN.get(m2,1)
        block='\n'.join(lines[i:i+12])
        nums=list(dict.fromkeys(int(x) for x in num_rx.findall(block) if 1<=int(x)<=90))
        if len(nums)>=8:
            six,jolly,ss=nums[:6],nums[6],nums[7]
            if len(set(six))==6:
                try: wd=dt_date(y2,mn,d2).weekday(); date_it=f"{GIORNI[wd]} {d2} {MESI_IT[mn]} {y2}"
                except: date_it=f"{d2} {MESI_IT[mn]} {y2}"
                oh=len(set(OUR)&set(six)); w=calc_wins(six)
                entry={'date':date_it,'numbers':six,'jolly':jolly,'superstar':ss,'our_hits':oh,'wins':w}
                if not any(r['numbers']==six for r in results):
                    results.append(entry)
                    print(f'  {date_it}: {six} J:{jolly} - hits:{oh}')
    i+=1

if not results:
    print('Parser non ha trovato risultati')
    sys.exit(0)

# Merge con esistenti (evita duplicati)
existing_nums={tuple(d['numbers']) for d in existing}
new_entries=[r for r in results if tuple(r['numbers']) not in existing_nums]
print(f'Nuove estrazioni: {len(new_entries)}')

merged=results + [d for d in existing if tuple(d['numbers']) not in {tuple(r['numbers']) for r in results}]
merged=merged[:120]  # max 120 storico

with open('data.json','w',encoding='utf-8') as f:
    json.dump({'updated':datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),'draws':merged},f,ensure_ascii=False,indent=2)
print(f'Salvate {len(merged)} estrazioni totali')
