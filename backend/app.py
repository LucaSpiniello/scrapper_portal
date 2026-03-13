import asyncio
import json
import uuid
from dataclasses import asdict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

from .scraper import (
    PortalScraper,
    ScraperFilters,
    build_search_url,
    validate_portal_url,
    properties_to_csv,
    PropertyData,
)

app = FastAPI(title="Portal Inmobiliario Scraper")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active sessions and their results
sessions: dict[str, dict] = {}


class ScrapeRequest(BaseModel):
    mode: str  # "filters" or "url"
    url: Optional[str] = None
    operacion: str = "venta"
    tipo_propiedad: str = "departamento"
    region: str = ""
    comuna: str = ""
    precio_min: Optional[int] = None
    precio_max: Optional[int] = None
    superficie_min: Optional[int] = None
    superficie_max: Optional[int] = None
    habitaciones: Optional[int] = None
    banos: Optional[int] = None
    estacionamiento: bool = False
    bodega: bool = False
    amoblado: bool = False
    max_pages: int = 5
    max_properties: int = 50


@app.websocket("/ws/scrape")
async def websocket_scrape(ws: WebSocket):
    await ws.accept()
    session_id = str(uuid.uuid4())
    scraper = None

    try:
        # Receive configuration
        data = await ws.receive_text()
        config = json.loads(data)
        req = ScrapeRequest(**config)

        # Determine URL
        if req.mode == "url":
            if not req.url or not validate_portal_url(req.url):
                await ws.send_json({
                    "type": "error",
                    "message": "URL inválida. Debe ser del dominio portalinmobiliario.com",
                })
                return
            search_url = req.url
        else:
            filters = ScraperFilters(
                operacion=req.operacion,
                tipo_propiedad=req.tipo_propiedad,
                region=req.region,
                comuna=req.comuna,
                precio_min=req.precio_min,
                precio_max=req.precio_max,
                superficie_min=req.superficie_min,
                superficie_max=req.superficie_max,
                habitaciones=req.habitaciones,
                banos=req.banos,
                estacionamiento=req.estacionamiento,
                bodega=req.bodega,
                amoblado=req.amoblado,
            )
            search_url = build_search_url(filters)

        await ws.send_json({
            "type": "info",
            "message": f"URL de búsqueda: {search_url}",
            "search_url": search_url,
        })

        # Progress callback
        async def on_progress(data: dict):
            try:
                await ws.send_json(data)
            except Exception:
                pass

        scraper = PortalScraper(on_progress=on_progress)
        sessions[session_id] = {"scraper": scraper, "properties": []}

        # Listen for cancel in background
        async def listen_for_cancel():
            try:
                while True:
                    msg = await ws.receive_text()
                    parsed = json.loads(msg)
                    if parsed.get("action") == "cancel":
                        scraper.cancel()
                        break
            except (WebSocketDisconnect, Exception):
                pass

        cancel_task = asyncio.create_task(listen_for_cancel())

        # Run scraper
        properties = await scraper.scrape(
            url=search_url,
            max_pages=req.max_pages,
            max_properties=req.max_properties,
        )

        sessions[session_id]["properties"] = properties

        # Send session ID for CSV download
        await ws.send_json({
            "type": "session",
            "session_id": session_id,
        })

        cancel_task.cancel()

    except WebSocketDisconnect:
        if scraper:
            scraper.cancel()
    except Exception as e:
        try:
            await ws.send_json({
                "type": "error",
                "message": f"Error: {str(e)}",
            })
        except Exception:
            pass
    finally:
        if scraper:
            await scraper.close_browser()


@app.get("/api/download/{session_id}")
async def download_csv(session_id: str):
    session = sessions.get(session_id)
    if not session or not session.get("properties"):
        return Response(content="No hay datos disponibles", status_code=404)

    csv_content = properties_to_csv(session["properties"])
    return Response(
        content=csv_content.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=propiedades_portal_inmobiliario.csv",
        },
    )


@app.get("/api/preview/{session_id}")
async def preview_data(session_id: str):
    session = sessions.get(session_id)
    if not session or not session.get("properties"):
        return {"properties": []}
    return {
        "properties": [asdict(p) for p in session["properties"]],
    }


# Serve frontend
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
