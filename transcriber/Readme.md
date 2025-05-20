# Transcriber Redis Consumers

Este proyecto proporciona un conjunto de consumidores asíncronos en Python que extraen tareas de transcripción desde 
Redis, las procesan con lógica de reintentos y envían los trabajos completados a una cola de auditoría.

---

## 📖 Descripción

El script monta varios “transcribers” que:

1. **Escuchan** una lista de tareas pendientes (`transcription_jobs`) en Redis.  
2. **Mueven** cada trabajo de la cola principal a una cola de procesamiento (`processing_jobs`) de manera atómica (usando `BRPOPLPUSH`).  
3. **Procesan** la tarea (por ahora, simplemente imprimen el nombre de archivo, pero en un futuro van a llamar a un modelo de transcripción)
4. Si el procesamiento **falla**, reencolan el trabajo en la cola principal e incrementan un contador de `attempts`.  
5. Si el procesamiento **tiene éxito**, trasladan el elemento a la cola de auditoría (`processed_jobs`).

Este flujo garantiza que:

- No se pierdan trabajos en caso de fallo.  
- Cada tarea se procesa al menos hasta que tenga éxito.  
- Queda un registro de todas las tareas completadas para auditoría.