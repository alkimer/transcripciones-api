import subprocess
import tempfile
import os
import datetime
import requests
import whisper
import time
import socket
import json
from yt_dlp import YoutubeDL

def check_internet(host="8.8.8.8", port=53, timeout=2):
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except Exception:
        return False

class YouTubeLiveTranscriber:
    def __init__(
        self,
        url: str,
        api_url: str,
        fuente: str,
        model_size: str = "base",
        intervalo: int = 15,
        resumen_palabras_inicio: int = 5,
        resumen_palabras_fin: int = 5,
        guardar_backup_local: bool = True,
        backup_file: str = "backup_transcripciones.jsonl"
    ):
        self.original_url = url
        self.api_url = api_url
        self.fuente = fuente
        self.model = whisper.load_model(model_size)
        self.intervalo = intervalo
        self.resumen_inicio = resumen_palabras_inicio
        self.resumen_fin = resumen_palabras_fin
        self.guardar_backup_local = guardar_backup_local
        self.backup_file = backup_file

        # 🎯 Extraemos info UNA sola vez para detectar live vs VOD
        info, stream_url = self._extract_info()
        self.is_live = bool(info.get("is_live", False))
        self.stream_url = stream_url

        # sólo relevante en VOD
        self.offset = 0.0

    def _extract_info(self):
        """
        Usa yt_dlp para extraer metadata e URL real de audio.
        """
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best"
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(self.original_url, download=False)
            audio_url = info.get("url")
            return info, audio_url

    def _grabar_segmento(self, duracion: int = None) -> str:
        """
        Graba un segmento de audio de `duracion` segundos:
         - Si es VOD, añade "-ss offset" para avanzar dentro del archivo.
         - Si es live, graba siempre desde "ahora" del stream.
        """
        dur = duracion or self.intervalo
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()

        cmd = ["ffmpeg", "-y"]
        if not self.is_live and self.offset > 0:
            # para VOD, saltamos self.offset segundos
            cmd += ["-ss", str(self.offset)]
        cmd += [
            "-i", self.stream_url,
            "-vn",
            "-ac", "1",
            "-ar", "16000",
            "-t", str(dur),
            tmp.name
        ]

        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # avanzamos offset SOLO en VOD
        if not self.is_live:
            self.offset += dur

        return tmp.name

    def _transcribir(self, audio_path: str) -> str:
        result = self.model.transcribe(audio_path, fp16=False)
        return result["text"].strip()
    #
    # def _guardar_backup(self, payload: dict):
    #     try:
    #         with open(self.backup_file, "a", encoding="utf-8") as f:
    #             f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    #     except Exception as e:
    #         print(f"⚠️ Error al guardar backup local: {e}")

    def run(self):
        print(f"Consumiendo Audio y almacenando chunks {'LIVE' if self.is_live else 'VOD'} cada {self.intervalo}s... (Ctrl+C para detener)")
        try:
            while True:
                inicio_chunk = time.time()
                t0 = datetime.datetime.utcnow()

                print(f"\n🎙️ [{t0.isoformat()}] Grabando audio...")
                try:
                    fichero = self._grabar_segmento()
                except Exception as e:
                    print(f"❌ Error al grabar segmento: {e}")
                    if not check_internet():
                        print("⚠️ Posible pérdida de conexión a internet")
                    time.sleep(5)
                    continue

                grabacion_time = time.time()
                print(f"✅ Audio grabado en {grabacion_time - inicio_chunk:.2f}s")

                # print("🧠 Transcribiendo...")
                # try:
                #     texto = self._transcribir(fichero)
                # except Exception as e:
                #     print(f"❌ Error en la transcripción: {e}")
                #     os.remove(fichero)
                #     continue
                # os.remove(fichero)
                # transcripcion_time = time.time()
                #
                # # Resumen visual
                # palabras = texto.split()
                # if len(palabras) > self.resumen_inicio + self.resumen_fin:
                #     inicio = " ".join(palabras[:self.resumen_inicio])
                #     fin = " ".join(palabras[-self.resumen_fin:])
                #     puntos = "." * (len(palabras) - (self.resumen_inicio + self.resumen_fin))
                #     resumen = f"{inicio} {puntos} {fin}"
                # else:
                #     resumen = texto
                #
                # t1 = datetime.datetime.utcnow()
                # print(f"[{t1.isoformat()}] {resumen} ({len(texto)} caracteres)")
                # print(f"🕒 Transcripción duró {transcripcion_time - grabacion_time:.2f}s")
                #
                # payload = {
                #     "fuente": self.fuente,
                #     "timestamp_inicio": t0.isoformat() + "Z",
                #     "timestamp_fin":    t1.isoformat() + "Z",
                #     "texto":            texto
                # }
                #
                # if self.guardar_backup_local:
                #     self._guardar_backup(payload)

                # Envío a API
                try:
                    print("📡 Enviando a API...")
                    resp = requests.post(self.api_url, json=payload, timeout=10)
                    resp.raise_for_status()
                    print(f"✅ Enviado a API ({resp.status_code})")
                except requests.exceptions.Timeout:
                    print("⏱️ Timeout al enviar a API")
                except requests.exceptions.ConnectionError:
                    print("❌ Error de red al conectar con la API")
                    if not check_internet():
                        print("⚠️ Posible pérdida de conexión a internet")
                except Exception as e:
                    print(f"❌ Error desconocido al enviar: {e}")

                # Asegurar intervalo constante
                total_time = time.time() - inicio_chunk
                if total_time < self.intervalo:
                    time.sleep(self.intervalo - total_time)

        except KeyboardInterrupt:
            print("🛑 Transcripción detenida por el usuario.")


if __name__ == "__main__":
    URL_YT = "https://www.youtube.com/watch?v=LWRr4MEECcQ"
    API    = "http://localhost:8000/transcripciones"
    FTE    = "YouTubeLive"

    transcriptor = YouTubeLiveTranscriber(
        url=URL_YT,
        api_url=API,
        fuente=FTE,
        model_size="small",
        intervalo=15,
        resumen_palabras_inicio=5,
        resumen_palabras_fin=5,
        guardar_backup_local=True
    )
    transcriptor.run()
