import asyncio
import datetime
import json
import logging
import os
from multiprocessing.pool import worker

import redis.asyncio as aioredis
from dotenv import load_dotenv


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

async def consumer(name: str, redis: aioredis.Redis, queue: str, processing_queue: str, transcribed_queue: str):
    logger.info(f"Transcriber {name} iniciado, escuchando '{queue}'")
    while True:
        try:
            payload = await redis.brpoplpush(queue, processing_queue)
            job = json.loads(payload)
            logger.info(f"[{name}] Recibido: {job}")

            try:
                # --- Aqui iría la lógica real de transcripción ---
                print(f"[{name}] Transcribiendo archivo: {job.get('file_name')}")

                # marcar fecha de transcripción
                job['transcription_date'] = datetime.datetime.utcnow().isoformat()

                # eliminar de procesamiento y enviar a transcribed_files_no_deleted
                await redis.lrem(processing_queue, 1, payload)
                new_payload = json.dumps(job)
                await redis.lpush(transcribed_queue, new_payload)
                logger.info(f"[{name}] Job enviado a '{transcribed_queue}': {job}")

            except Exception as process_err:
                # en caso de falla, reencolar con contador de intentos
                await redis.lrem(processing_queue, 1, payload)
                attempts = job.get('attempts', 0) + 1
                job['attempts'] = attempts
                new_payload = json.dumps(job)
                await redis.lpush(queue, new_payload)
                logger.error(f"[{name}] Error procesando {job}, reintento #{attempts}: {process_err}")

        except Exception as e:
            logger.error(f"[{name}] Error en bucle de consumo: {e}")
            await asyncio.sleep(1)

async def main(redis_url: str, queue: str, processing_queue: str, transcribed_queue: str, workers: int):
    redis = aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
    try:
        tasks = []
        for i in range(workers):
            name = f"worker-{i+1}"
            tasks.append(asyncio.create_task(
                consumer(name, redis, queue, processing_queue, transcribed_queue)
            ))
        await asyncio.gather(*tasks)
    finally:
        await redis.close()

if __name__ == '__main__':
    # Carga variables desde .env
    load_dotenv()

    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = os.getenv("REDIS_PORT", "6379")
    # Construimos la URL como string, no el cliente
    redis_url = f"redis://{redis_host}:{redis_port}"

    workers = int(os.getenv("WORKERS", "3"))
    pending_transcription_queue      = os.getenv("REDIS_QUEUE_TRANSCRIPTION_JOB")
    in_process_queue                = os.getenv("REDIS_QUEUE_IN_TRANSCRIPTION_PROCESS")
    transcribed_not_deleted_queue   = os.getenv("REDIS_QUEUE_TRANSCRIBED_FILES_NOT_DELETED_JOB")

    logger.info(
        f"Iniciando {workers} workers en '{pending_transcription_queue}' → "
        f"una vez procesados enviar a: '{transcribed_not_deleted_queue}', redis url: {redis_url}"
    )

    try:
        # Aquí pasamos el *string* redis_url, no el cliente
        asyncio.run(main(
            redis_url,
            pending_transcription_queue,
            in_process_queue,
            transcribed_not_deleted_queue,
            workers
        ))
    except KeyboardInterrupt:
        logger.info("Deteniendo transcribers…")
