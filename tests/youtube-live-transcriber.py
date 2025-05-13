import subprocess
import tempfile
import os
import datetime
import requests
import whisper
from yt_dlp import YoutubeDL  # 👈 NUEVO

class YouTubeLiveTranscriber:
    def __init__(self, url: str, api_url: str, fuente: str, model_size: str = "base"):
        self.original_url = url
        self.api_url = api_url
        self.fuente = fuente
        self.model = whisper.load_model(model_size)
        self.stream_url = self._get_audio_stream_url()  # 👈 OBTENER URL REAL

    def _get_audio_stream_url(self) -> str:
        """
        Usa yt_dlp para obtener la URL real del stream de audio.
        """
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best"
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(self.original_url, download=False)
            return info['url']

    def _grabar_segmento(self, duracion: int = 15) -> str:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        cmd = [
            "ffmpeg",
            "-y",
            "-i", self.stream_url,  # 👈 USAMOS LA URL REAL
            "-vn",
            "-ac", "1",
            "-ar", "16000",
            "-t", str(duracion),
            tmp.name
        ]
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return tmp.name

    def _transcribir(self, audio_path: str) -> str:
        result = self.model.transcribe(audio_path, fp16=False)
        return result["text"].strip()

    def run(self):
        print("Iniciando transcripción en vivo... (Ctrl+C para detener)")
        try:
            while True:
                t0 = datetime.datetime.utcnow()
                fichero = self._grabar_segmento(15)
                t1 = datetime.datetime.utcnow()

                texto = self._transcribir(fichero)
                os.remove(fichero)

                # 👇 Mostrar resumen visual
                palabras = texto.split()
                if len(palabras) > 10:
                    inicio = " ".join(palabras[:5])
                    fin = " ".join(palabras[-5:])
                    puntos = "." * (len(palabras) - 10)
                    resumen = f"{inicio} {puntos} {fin}"
                else:
                    resumen = texto  # si tiene pocas palabras, mostrarlo todo

                print(f"[{t1.isoformat()}] {resumen} ({len(texto)} caracteres)")

                payload = {
                    "fuente": self.fuente,
                    "timestamp_inicio": t0.isoformat() + "Z",
                    "timestamp_fin": t1.isoformat() + "Z",
                    "texto": texto
                }

                try:
                    resp = requests.post(self.api_url, json=payload)
                    resp.raise_for_status()
                except requests.RequestException as e:
                    print(f"Error al enviar transcripción: {e}")

        except KeyboardInterrupt:
            print("Transcripción detenida por el usuario.")


if __name__ == "__main__":
    URL_YT = "https://www.youtube.com/watch?v=LWRr4MEECcQ"
    API    = "http://localhost:8000/transcripciones"
    FTE    = "YouTubeLive"

    transcriptor = YouTubeLiveTranscriber(URL_YT, API, FTE, model_size="small")
    transcriptor.run()
