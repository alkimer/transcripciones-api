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

async def handle_chunk(chunk: AudioSegment, index: int, url: str, chunk_duration: int, redis: aioredis.Redis):
    """
    Procesa y guarda un único chunk: exporta a mp3 y crea el mensaje en Redis.
    """
    ID = str(uuid.uuid4())
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    url_slug = sanitize_url(url)
    file_name = f"{timestamp}-{url_slug}-{ID}-{chunk_duration}-{index}.mp3"
    os.makedirs("../tests/audios", exist_ok=True)
    file_path = os.path.join("../tests/audios", file_name)

    # Guardar archivo mp3 de manera asíncrona
    await asyncio.to_thread(chunk.export, file_path, format="mp3")
    logger.info(f"Chunk {index} guardado en {file_path}")

    # Crear mensaje de trabajo y guardar en Redis
    transcription_job = {
        "id": ID,
        "file-name": file_name,
        "transcribed": "false"
    }

    await redis.rpush("transcription_jobs", json.dumps(transcription_job))
    logger.info(f"Mensaje guardado en Redis: {transcription_job}")

async def process_url(url: str, chunk_duration: int):
    # Conexión a Redis usando redis-py con soporte asyncio
    redis = aioredis.from_url("redis://localhost:6379", encoding="utf-8", decode_responses=True)
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
            tasks.append(asyncio.create_task(handle_chunk(chunk, index, url, chunk_duration, redis)))
            index += 1

        # Esperar a que todas las tareas terminen
        await asyncio.gather(*tasks)
    finally:
        await redis.aclose()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Extrae y procesa chunks de audio de un video de YouTube.")
    # parser.add_argument('url', help="URL del video de YouTube")
    # parser.add_argument('--chunk-duration', type=int, default=15,
    #                     help="Duración de cada chunk en segundos (por defecto: 15)")
    # args = parser.parse_args()
    URL_YT = "https://www.youtube.com/watch?v=LWRr4MEECcQ"
    CHUNK_DURATION = 15
    logger.info(f"Iniciando procesamiento de {URL_YT} con chunks de {CHUNK_DURATION}s")
    asyncio.run(process_url(URL_YT, 15))
