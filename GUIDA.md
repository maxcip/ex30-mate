# Guida all'Utilizzo — Volvo EX30 Mate

**Volvo EX30 Mate** è un'applicazione web completa per il monitoraggio in tempo reale, lo storico dei viaggi, la gestione delle ricariche, i costi e il controllo remoto della tua Volvo EX30 (con supporto completo alla modalità DEMO per testare l'app senza un veicolo connesso).

---

## 🚀 Avvio Rapido

Puoi avviare l'applicazione in due modi:

### 1. Tramite Docker Compose (Consigliato)
Assicurati di avere Docker e Docker Compose installati, quindi nella cartella `ex30-mate` esegui:
```bash
docker compose up --build
```
L'applicazione sarà disponibile all'indirizzo: **http://192.168.10.137:4000**

### 2. Esecuzione Locale (Python)
Installa le dipendenze e avvia il server uvicorn:
```bash
cd ex30-mate
pip install -r requirements.txt python-multipart
# Imposta la modalità demo (opzionale se non hai chiavi API Volvo)
export VOLVO_DEMO=1
export DATA_DIR=./data

# Avvia il server
python3 -m uvicorn web.main:app --host 192.168.10.137 --port 4000
```

---

## 🎛 Funzionalità Principali (Pagine Web)

1. **Panoramica (`/`)**: 
   - Stato live della batteria (SoC %), autonomia residua, chilometraggio, temperature (abitacolo, batteria, esterno).
   - Pulsanti di controllo rapido (Blocca/Sblocca porte, Avvia/Ferma ricarica).
   - Widget dell'ultima ricarica e ultimi viaggi effettuati con mappa interattiva.
   
2. **Viaggi (`/trips`)**:
   - Storico completo di tutti i percorsi registrati con data, ora, indirizzi di partenza/arrivo, durata, distanza e consumo energetico specifico (Wh/km).

3. **Mappa (`/map`)**:
   - Visualizzazione geografica interattiva (Leaflet + OpenStreetMap) con tracciato dei percorsi e ultima posizione nota del veicolo.

4. **Ricariche (`/charges`)**:
   - Elenco dettagliato delle ricariche AC (Wallbox) e DC (colonnine rapide), con energia immessa, durata, potenza massima e costo stimato o reale.

5. **Costi (`/costs`)**:
   - Analisi finanziaria delle spese di ricarica, riepilogo per tipologia (AC vs DC) e grafico a barre dei costi per sessione.

6. **Statistiche (`/statistics`)**:
   - Grafici avanzati (ApexCharts) sull'andamento della batteria nel tempo, consumo nel corso dei viaggi e distribuzione dell'efficienza energetica.

7. **Batteria (`/battery`)**:
   - Monitoraggio approfondito della salute della batteria, temperature e curva di potenza durante la ricarica.

8. **Comandi (`/commands`)**:
   - Pannello di controllo remoto per inviare comandi al veicolo (clacson, fari, precondizionamento clima, apertura bagagliaio).

9. **Navigazione (`/navigation`)**:
   - Invio rapido di destinazioni di navigazione direttamente al sistema di bordo dell'auto.

10. **Impostazioni (`/settings`)**:
    - Cambio lingua (Italiano / English), valuta (EUR, USD, GBP, SEK) e configurazione generale.

---

## ⚙️ Configurazione con Veicolo Reale (API Volvo)

Per connettere l'app alla tua Volvo EX30 reale anziché usare la modalità DEMO:

1. Registrati sul portale **Volvo Developer** e ottieni le tue chiavi API (`VOLVO_API_KEY` e `VOLVO_VCC_API_KEY`).
2. Configura le variabili d'ambiente nel file `docker-compose.yml` o nel tuo ambiente di esecuzione:
   ```env
   VOLVO_DEMO=0
   VOLVO_API_KEY=tua_api_key
   VOLVO_VCC_API_KEY=tua_vcc_api_key
   VOLVO_VIN=Tuo_VIN_Veicolo
   ```
3. Il poller in background (`poller/main.py`) interrogherà periodicamente le API ufficiali Volvo salvando la telemetria nel database SQLite (`data/volvo_mate.db`).
