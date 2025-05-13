# Transcripciones API

Servicio de transcripción radial que permite:

- Guardar bloques de texto de 15s
- Consultar por rango, fuente o palabra

## Endpoints

### POST `/transcripciones/`
Crea un bloque de transcripción:

```json
{
  "fuente": "Radio Mitre",
  "timestamp_inicio": "2025-05-13T10:00:00",
  "timestamp_fin": "2025-05-13T10:00:15",
  "texto": "Texto del audio"
}
```

## Tests
pytest tests/

## Run

docker-compose build --no-cache
docker-compose up

