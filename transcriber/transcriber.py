import asyncio
import json
import argparse
import logging
import redis.asyncio as aioredis

# Configuración de logging
def setup_logger():
    logger = logging.getLogger("transcriber")
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger

logger = setup_logger()

async def consumer(name: str, redis: aioredis.Redis, queue: str, processing_queue: str, audit_queue: str):
    """
    Consume jobs de Redis usando BRPOPLPUSH:
    - Toma la tarea de 'queue' y la mueve a 'processing_queue' atómicamente.
    - Procesa la tarea.
    - Si falla, reencola incrementando el campo 'attempts'.
    - Si tiene éxito, mueve la tarea a 'audit_queue'.
    """
    logger.info(f"Transcriber {name} iniciado, escuchando '{queue}'")
    while True:
        try:
            # Mover job de queue a processing_queue
            payload = await redis.brpoplpush(queue, processing_queue)
            job = json.loads(payload)
            logger.info(f"Transcriber {name} recibió job: {job}")

            try:
                # Procesamiento real (por ahora, solo imprimir)
                print(f"Procesando archivo: {job.get('file-name')}")

                # Éxito: eliminar de processing_queue y archivar
                await redis.lrem(processing_queue, 1, payload)
                await redis.lpush(audit_queue, payload)
                logger.info(f"Consumer {name} movió job a '{audit_queue}' para auditoría: {job}")

            except Exception as process_err:
                # Fallo: reencolar con contador de intentos
                await redis.lrem(processing_queue, 1, payload)
                attempts = job.get('attempts', 0) + 1
                job['attempts'] = attempts
                new_payload = json.dumps(job)
                await redis.lpush(queue, new_payload)
                logger.error(f"Error procesando job {job}, reencolado intento #{attempts}: {process_err}")

        except Exception as e:
            logger.error(f"Error en ciclo consumer {name}: {e}")
            await asyncio.sleep(1)

async def main(redis_url: str, queue: str, processing_queue: str, audit_queue: str, workers: int):
    redis = aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
    try:
        tasks = []
        for i in range(workers):
            name = f"worker-{i+1}"
            tasks.append(asyncio.create_task(
                consumer(name, redis, queue, processing_queue, audit_queue)
            ))
        await asyncio.gather(*tasks)
    finally:
        await redis.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Transcriber Redis consumers con reintentos y auditoría.")
    parser.add_argument('--redis-url', default='redis://localhost:6379', help='URL de Redis')
    parser.add_argument('--queue', default='transcription_jobs', help='Lista principal de jobs')
    parser.add_argument('--processing-queue', default='processing_jobs', help='Lista de jobs en procesamiento')
    parser.add_argument('--audit-queue', default='processed_jobs', help='Lista de jobs procesados para auditoría')
    parser.add_argument('--workers', type=int, default=3, help='Número de consumidores concurrentes')
    args = parser.parse_args()

    logger.info(
        f"Iniciando {args.workers} consumer(s) para '{args.queue}' en {args.redis_url}. "
        f"Processing: '{args.processing_queue}', Audit: '{args.audit_queue}'"
    )
    try:
        asyncio.run(
            main(
                args.redis_url,
                args.queue,
                args.processing_queue,
                args.audit_queue,
                args.workers
            )
        )
    except KeyboardInterrupt:
        logger.info("Deteniendo consumers...")
