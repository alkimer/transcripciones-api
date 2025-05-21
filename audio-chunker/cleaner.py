import asyncio
import json
import argparse
import logging
import datetime
import os
import redis.asyncio as aioredis
from dotenv import load_dotenv
import os

def setup_logger():
    logger = logging.getLogger("cleaner")
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger

logger = setup_logger()

async def cleaner(redis: aioredis.Redis, transcribed_queue: str, completed_queue: str):
    logger.info(f"Cleaner iniciado, leyendo de '{transcribed_queue}'")
    while True:
        try:
            payload = await redis.lpop(transcribed_queue)
            if not payload:
                await asyncio.sleep(1)
                continue

            job = json.loads(payload)
            file_path = job.get('file-path')

            try:
                os.remove(file_path)
                # marcar fecha de borrado
                job['file_deleted_date'] = datetime.datetime.utcnow().isoformat()
                # enviar a completed_jobs
                new_payload = json.dumps(job)
                await redis.lpush(completed_queue, new_payload)
                logger.info(f"Archivo '{file_path}' borrado. Job enviado a '{completed_queue}': {job}")
            except Exception as del_err:
                # si falla el borrado, reenviar para reintento
                await redis.lpush(transcribed_queue, payload)
                logger.error(f"No se pudo borrar '{file_path}', reencolando: {del_err}")

        except Exception as e:
            logger.error(f"Error en bucle cleaner: {e}")
            await asyncio.sleep(1)

async def main(redis_url: str, transcribed_queue: str, completed_queue: str):
    redis = aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
    try:
        await cleaner(redis, transcribed_queue, completed_queue)
    finally:
        await redis.close()

if __name__ == '__main__':
    load_dotenv()

    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = os.getenv("REDIS_PORT", "6379")
    # Construimos la URL como string, no el cliente
    redis_url = f"redis://{redis_host}:{redis_port}"
    transcribed_not_deleted_queue   = os.getenv("REDIS_QUEUE_TRANSCRIBED_FILES_NOT_DELETED_JOB")
    transcribed_and_deleted_queue   = os.getenv("REDIS_QUEUE_TRANSCRIBED_DELETED")

    logger.info(f"Iniciando cleaner: de '{transcribed_not_deleted_queue}' → '{transcribed_and_deleted_queue}'")
    try:
        asyncio.run(main(
            redis_url,
            transcribed_not_deleted_queue,
            transcribed_and_deleted_queue
        ))
    except KeyboardInterrupt:
        logger.info("Deteniendo cleaner…")
