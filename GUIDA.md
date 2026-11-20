# Guida all'utilizzo | Volvo EX30 Mate

Volvo EX30 Mate è un'applicazione web per il monitoraggio del veicolo, lo storico dei viaggi, le ricariche, i costi e la posizione.

## Avvio rapido

### Docker Compose

Nella cartella del progetto:

```bash
docker compose up --build
```

L'applicazione è disponibile su:

```text
http://IP_DEL_SERVER:4000
```

### Aggiornamento su Proxmox

Se il container è già installato con Docker Compose:

```bash
cd /percorso/di/ex30-mate

git fetch origin
git checkout update-trip-maps-vehicle
git pull origin update-trip-maps-vehicle

docker compose build --no-cache
docker compose up -d
```

Verifica l'avvio:

```bash
docker compose ps
docker compose logs -f --tail 100 volvo-ex30-mate
```

Il volume `./data:/data` mantiene il database, la cronologia dei viaggi e le impostazioni. La ricostruzione dell'immagine non cancella questi dati.

## Pagine disponibili

### Panoramica

La Vista principale mostra:

- Stato della batteria, autonomia residua, chilometraggio e temperature.
- Dati principali del veicolo, inclusi autonomia, efficienza, energia consumata e costo totale.
- Ultima ricarica.
- Ultima posizione su mappa.
- Viaggi recenti.

I comandi rapidi di blocco, sblocco, avvio e arresto ricarica non sono più presenti nella Vista principale.

### Viaggi

La pagina Viaggi mostra ogni viaggio in una card con:

- Data e ora.
- Indirizzo di partenza e destinazione.
- Distanza, durata ed efficienza.
- Modalità di guida.
- Mini mappa cliccabile del percorso.

Il click sulla mini mappa apre la mappa completa del viaggio, con il tracciato e l'adattamento automatico della vista.

### Mappa

La pagina Mappa mostra l'ultima posizione nota del veicolo e i percorsi dei viaggi.

### Ricariche

La pagina Ricariche mostra le sessioni AC e DC, con energia, durata, potenza massima e costi.

### Costi

La pagina Costi mostra le spese di ricarica, il confronto tra AC e DC e i costi per sessione.

### Statistiche

La pagina Statistiche mostra grafici su batteria, consumi, efficienza e viaggi.

### Batteria

La pagina Batteria mostra salute della batteria, temperature e curva di potenza durante la ricarica.

### Veicolo

La pagina Veicolo mostra:

- VIN.
- Capacità batteria.
- Colore: Cloud Blue.
- Anno: 2026.
- Modello.

La sezione Current Status mostra:

- Batteria.
- Autonomia.
- Chilometraggio.

Velocità, marcia e stato non sono più mostrati.

### Impostazioni

La pagina Impostazioni consente di configurare lingua, valuta, Home Assistant, posizione di casa e altre opzioni.

## Configurazione con veicolo reale

Per connettere l'app alla Volvo EX30 reale:

1. Registrati sul portale Volvo Developer.
2. Ottieni `VOLVO_API_KEY` e `VOLVO_VCC_API_KEY`.
3. Configura le variabili nel file `docker-compose.yml` oppure nel file `.env`:

```env
VOLVO_DEMO=0
VOLVO_API_KEY=tua_api_key
VOLVO_VCC_API_KEY=tua_vcc_api_key
VOLVO_VIN=Tuo_VIN_Veicolo
```

Il poller interroga periodicamente le API Volvo e salva i dati nel database SQLite in `data/volvo_mate.db`.

## Modalità demo

Per testare l'app senza un veicolo connesso:

```env
VOLVO_DEMO=1
```

La modalità demo genera dati di esempio e non invia comandi reali al veicolo.
