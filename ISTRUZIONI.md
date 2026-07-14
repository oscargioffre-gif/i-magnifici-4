# I Magnifici 4 — Pacchetto per repo pubblico

## Dove va ogni file

| File | Destinazione nel repo | Azione |
|---|---|---|
| `update.yml` | `.github/workflows/update.yml` | **Sostituisci** quello esistente |
| `fetch.py` | `fetch.py` (radice del repo) | **Sostituisci** quello esistente |
| `index.html` | `index.html` (radice) | **NON sostituire** — solo la micro-patch qui sotto |
| `data.json` | radice | **Non toccare** (lo gestisce il workflow) |

## Procedura (2 minuti, tutto da browser GitHub)

1. Apri `.github/workflows/update.yml` → matita (Edit) → incolla il nuovo contenuto → **Commit changes**.
2. Apri `fetch.py` → matita → incolla il nuovo contenuto → **Commit changes**.
3. Vai su **Actions → Aggiorna estrazioni SuperEnalotto → Run workflow** (lancio manuale di collaudo).
4. Apri il log del run: ogni estrazione letta viene stampata come
   `✓ Sabato 4 Luglio 2026: [2, 37, 55, 62, 72, 76]  J:34  SS:75`.
   Confronta 2-3 righe col sito ufficiale: se combaciano, sei a posto per sempre.
5. Verifica finale: apri `https://oscargioffre-gif.github.io/i-magnifici-4/data.json`
   e poi l'app.

## Patch di sicurezza per index.html (repo pubblico = chiave esposta)

Nell'`index.html` ci sono queste due righe (sezione `<script>`, vicino a `const OUR`):

```js
const JSONBIN_ID='69aec110d0ea881f4000406f';
const JSONBIN_KEY='$2a$10$f2iA...';                 // ← MASTER KEY esposta!
...
const BIN_HDR={'Content-Type':'application/json','X-Master-Key':JSONBIN_KEY};
```

La **Master Key** dà controllo TOTALE sul tuo account JSONbin: con il repo
pubblico chiunque può leggerla e cancellare/modificare il fondocassa o creare
bin a tuo nome. Rimedio in 3 passi:

1. Su **jsonbin.io → API Keys**: clicca **Regenerate** sulla Master Key
   (invalida quella vecchia già esposta — questo è il passo più importante).
2. Sempre lì, crea una **Access Key** nuova con permessi *Read + Update*
   limitati ai **Bins** (non dare Delete né Create).
3. In `index.html` modifica SOLO queste due righe (niente altro, i Base64
   restano intatti):

```js
const JSONBIN_KEY='<LA-NUOVA-ACCESS-KEY>';
const BIN_HDR={'Content-Type':'application/json','X-Access-Key':JSONBIN_KEY};
```

Nota: `X-Master-Key` → `X-Access-Key` (JSONbin usa header diversi per i due
tipi di chiave). Così, anche se la Access Key resta visibile nel sorgente,
il danno massimo possibile è scrivere nel singolo bin del fondocassa — la
tua Master Key e il resto dell'account restano al sicuro.

## Cosa fa il nuovo workflow

- Gira **Mar/Gio/Ven/Sab alle 21:00 italiane** tutto l'anno (doppio cron
  19:00 + 20:00 UTC per coprire ora legale e solare; la corsa doppia è
  innocua perché fetch.py non committa se non c'è nulla di nuovo).
- `actions/checkout@v5` → sparisce il warning Node 20/24.
- Committa `data.json` solo se cambiato (niente commit a vuoto).
- Pulsante **Run workflow** sempre disponibile per aggiornamenti manuali.

## Cosa garantisce il nuovo fetch.py (già collaudato con test)

- **Storico indistruttibile**: fonde le nuove estrazioni con quelle già in
  data.json, non cancella mai nulla.
- **Anti-shift**: sestina ancorata all'etichetta "Jolly" → numeri di concorso
  e date non fanno più scorrere i valori (bug del 7 marzo risolto per costruzione).
- **Fail-safe**: se il sito sorgente non risponde, data.json resta intatto.
- **Schema pulito**: scrive solo date/numbers/jolly/superstar; le vincite dei
  Magnifici 4 le calcola il frontend (unica fonte di verità: `OUR` in index.html).
