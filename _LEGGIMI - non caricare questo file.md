# Da caricare su GitHub — repo `i-magnifici-4`

Questa cartella rispecchia la struttura del repository: ogni file va caricato
nella stessa posizione in cui si trova qui dentro.

**Questo file (_LEGGIMI) NON va caricato** — serve solo come promemoria locale.

## ⚡ DA CARICARE ADESSO (aggiornato al 18/07/2026)

| File | Dove va nel repo | Perché |
|---|---|---|
| `index.html` | radice (sostituisci) | Nuova sezione "I PIÙ ESTRATTI" + chiave JSONbin sicura (Access Key) |
| `.github/workflows/update.yml` | `.github/workflows/` (sostituisci) | Workflow nuovo: doppio cron ora legale/solare, niente commit a vuoto — sul repo c'è ancora quello vecchio |

## Già a posto sul repo (nessuna azione)

- `fetch.py` — identico a quello già caricato
- `README.md`, `icon.png` — invariati
- `data.json` — **mai caricarlo a mano**: lo gestisce il workflow

## Come caricare

1. Repo su GitHub → **Add file → Upload files** → trascina `index.html` → **Commit changes**
2. Apri `.github/workflows/update.yml` sul repo → matita (Edit) → incolla il contenuto del file qui dentro → **Commit changes**

## Regole

- `data.json` non va mai caricato a mano.
- Ogni volta che implementiamo una modifica, questa cartella viene aggiornata
  automaticamente con i file nuovi/modificati da caricare.
