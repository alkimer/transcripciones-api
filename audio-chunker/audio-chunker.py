import os
import re
import json
import uuid
import argparse
import asyncio
import logging
import datetime
import tempfile

from yt_dlp import YoutubeDL
from pydub import AudioSegment
import redis.asyncio as aioredis
from dotenv import load_dotenv
import os
# Configuración de logging
def setup_logger():
    logger = logging.getLogger("youtube_chunker")
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger

logger = setup_logger()

# Sanitiza la URL para usarla en el nombre de archivo
def sanitize_url(url: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "_", url)

async def download_audio(url: str) -> str:
    """
    Descarga el audio de YouTube como archivo mp3 en un archivo temporal.
    Devuelve la ruta al archivo mp3 descargado.
    """
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".%(ext)s")
    tmp_path = tmp.name
    tmp.close()
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': tmp_path,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True
    }
    logger.info(f"Descargando audio de {url}...")
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    mp3_path = tmp_path.replace('%(ext)s', 'mp3')
    logger.info(f"Audio descargado en {mp3_path}")
    return mp3_path

async def handle_chunk(chunk: AudioSegment, index: int, url: str, chunk_duration: int, redis: aioredis.Redis, media_name: str):
    """
    Procesa y guarda un único chunk: exporta a mp3 y crea el mensaje en Redis.
    """
    audio_chunks_path = os.getenv("AUDIO_CHUNKS_PATH")

    ID = str(uuid.uuid4())
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    url_slug = sanitize_url(url)
    file_name = f"{timestamp}-{url_slug}-{ID}-{chunk_duration}-{media_name}-{index}.mp3"
    os.makedirs(audio_chunks_path, exist_ok=True)
    file_path = os.path.join(audio_chunks_path, file_name)
    absolute_path = os.path.abspath(file_path)

    # Guardar archivo mp3 de manera asíncrona
    await asyncio.to_thread(chunk.export, absolute_path, format="mp3")
    logger.info(f"Chunk {index} guardado en {absolute_path}")

    # Crear mensaje de trabajo y guardar en Redis
    transcription_job = {
        "id": ID,
        "file-path": absolute_path,
        "media":  media_name
    }

    transcription_queue = os.getenv("REDIS_QUEUE_TRANSCRIPTION_JOB")
    await redis.rpush( transcription_queue, json.dumps(transcription_job))
    logger.info(f"Mensaje guardado en Redis: queue: {transcription_queue} job: {transcription_job}")

async def process_url(url: str, chunk_duration: int, media_name: str = None):
    # Conexión a Redis usando redis-py con soporte asyncio
    if media_name is None:
        raise Exception("media_name is None")

    redis_host = os.getenv("REDIS_HOST")
    redis_port = os.getenv("REDIS_PORT")
    redis = aioredis.from_url("redis://" + redis_host + ":" + redis_port, encoding="utf-8", decode_responses=True)
    try:
        # Descargar audio completo
        mp3_path = await download_audio(url)
        audio = await asyncio.to_thread(AudioSegment.from_file, mp3_path)
        duration_ms = len(audio)
        chunk_ms = chunk_duration * 1000

        tasks = []
        index = 1
        for start in range(0, duration_ms, chunk_ms):
            end = min(start + chunk_ms, duration_ms)
            chunk = audio[start:end]
            logger.debug(f"Procesando chunk {index}: {start}ms a {end}ms")
            tasks.append(asyncio.create_task(handle_chunk(chunk, index, url, chunk_duration, redis, media_name)))
            index += 1

        # Esperar a que todas las tareas terminen
        await asyncio.gather(*tasks)
    finally:
        await redis.aclose()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Extrae y procesa chunks de audio de un video de YouTube.")
    # Carga variables desde .env
    load_dotenv()

    # Obtiene el valor de DB_HOST y lo imprime

    # parser.add_argument('url', help="URL del video de YouTube")
    # parser.add_argument('--chunk-duration', type=int, default=15,
    #                     help="Duración de cada chunk en segundos (por defecto: 15)")
    # args = parser.parse_args()
    URL_YT = "https://www.youtube.com/watch?v=LWRr4MEECcQ"
    CHUNK_DURATION = 15
    logger.info(f"Iniciando procesamiento de {URL_YT} con chunks de {CHUNK_DURATION}s")
    media_name = "test-media"
    asyncio.run(process_url(URL_YT, int(os.getenv("AUDIO_CHUNK_DURATION_SECONDS")), media_name))
