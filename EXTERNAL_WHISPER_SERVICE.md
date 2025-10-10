# Migrazione a Servizio Whisper Esterno

## Modifiche Principali

Il bot è stato aggiornato per utilizzare un servizio esterno di trascrizione Whisper invece di eseguire il modello localmente. Questo riduce significativamente i requisiti di risorse del bot.

## Vantaggi

- **Riduzione delle risorse**: Non sono più necessari GPU, CUDA o grandi quantità di RAM
- **Scalabilità**: Il servizio di trascrizione può essere scalato indipendentemente dal bot
- **Manutenibilità**: Separazione delle responsabilità tra bot e servizio di trascrizione
- **Flessibilità**: Possibilità di utilizzare diversi provider di servizi Whisper

## Configurazione

### Variabili d'Ambiente

Aggiungi le seguenti variabili al tuo file `.env`:

```bash
# Opzione 1: URI completo (raccomandato)
WHISPER_SERVICE_URI=http://whisper-service:9000

# Opzione 2: Host e porta separati
WHISPER_SERVICE_HOST=whisper-service
WHISPER_SERVICE_PORT=9000
```

### Servizio Whisper ASR Webservice

Il bot è compatibile con [Whisper ASR Webservice](https://github.com/ahmetoner/whisper-asr-webservice).

Per avviare il servizio con Docker:

```bash
docker run -d -p 9000:9000 \
  --name whisper-service \
  --gpus all \
  onerahmet/openai-whisper-asr-webservice:latest
```

Per avviarlo con docker-compose, aggiungi al tuo `compose.yaml`:

```yaml
services:
  whisper-service:
    image: onerahmet/openai-whisper-asr-webservice:latest
    container_name: whisper-service
    restart: unless-stopped
    ports:
      - "9000:9000"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0']
              capabilities: [gpu]
    environment:
      - ASR_MODEL=turbo
      - ASR_ENGINE=openai_whisper
```

## Endpoint Utilizzati

### `/detect-language` (POST)
Rileva la lingua dell'audio fornito.

**Parametri:**
- `audio_file`: File audio (multipart/form-data)
- `encode`: Boolean, pre-elaborazione con FFmpeg (default: true)

**Risposta:**
```json
{
  "detected_language": "it",
  "language_probability": 0.95
}
```

### `/asr` (POST)
Trascrive l'audio nella lingua specificata.

**Parametri:**
- `audio_file`: File audio (multipart/form-data)
- `encode`: Boolean, pre-elaborazione con FFmpeg (default: true)
- `task`: "transcribe" o "translate" (default: "transcribe")
- `language`: Codice lingua ISO 639-1 (es: "it", "en", "es")
- `output`: Formato output: "txt", "json", "vtt", "srt", "tsv" (default: "txt")

**Risposta:**
Testo trascritto (formato dipende dal parametro `output`)

## Compatibilità

Il bot mantiene la cache delle trascrizioni nel database locale, quindi le trascrizioni già elaborate non verranno inviate nuovamente al servizio esterno.

## Requisiti di Sistema

### Prima (con Whisper locale)
- CPU: 2 core
- RAM: 6GB
- GPU: NVIDIA con CUDA support
- Spazio disco: ~10GB (modello Whisper)

### Dopo (con servizio esterno)
- CPU: 0.25-1 core
- RAM: 256-512MB
- GPU: Non necessaria
- Spazio disco: ~100MB

## Modifiche ai File

- `app/transcription.py`: Sostituiti i metodi Whisper locali con chiamate HTTP
- `app/utils.py`: Aggiunte variabili di configurazione per il servizio
- `compose.yaml`: Rimosse configurazioni GPU, ridotti requisiti di risorse
- `Dockerfile`: Rimossa installazione di PyTorch e Whisper
- `requirements.txt`: Rimossi torch/whisper, aggiunto requests

## Rollback

Per tornare alla versione con Whisper locale, esegui:
```bash
git checkout main
```
