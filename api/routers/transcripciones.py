from fastapi import APIRouter, HTTPException
import logging
from database import get_connection
from models import Transcripcion

router = APIRouter()
logger = logging.getLogger("api")
logging.basicConfig(level=logging.INFO)

@router.post("/")
def crear_transcripcion(transcripcion: Transcripcion):
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO transcripciones (fuente, timestamp_inicio, timestamp_fin, texto)
                    VALUES (%s, %s, %s, %s)
                """, (transcripcion.fuente, transcripcion.timestamp_inicio,
                      transcripcion.timestamp_fin, transcripcion.texto))
                logger.info(f"Transcripción creada: {transcripcion}")
        return {"ok": True}
    except Exception as e:
        logger.exception("Error al crear transcripción")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/buscar")
def buscar(fuente: str = None, desde: str = None, hasta: str = None, texto: str = None):
    conn = get_connection()
    query = "SELECT * FROM transcripciones WHERE TRUE"
    params = []

    if fuente:
        query += " AND fuente = %s"
        params.append(fuente)
    if desde:
        query += " AND timestamp_inicio >= %s"
        params.append(desde)
    if hasta:
        query += " AND timestamp_fin <= %s"
        params.append(hasta)
    if texto:
        query += " AND texto ILIKE %s"
        params.append(f"%{texto}%")

    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            resultados = cur.fetchall()
        return resultados
    except Exception as e:
        logger.exception("Error en la búsqueda")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
