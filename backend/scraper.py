import asyncio
import re
import csv
import io
from dataclasses import dataclass, asdict
from typing import Optional, Callable, Awaitable
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page, Browser, BrowserContext


BASE_URL = "https://www.portalinmobiliario.com"

OPERATION_MAP = {
    "venta": "venta",
    "arriendo": "arriendo",
}

PROPERTY_TYPE_MAP = {
    "casa": "casa",
    "departamento": "departamento",
    "parcela": "parcela",
    "oficina": "oficina",
    "local": "local-comercial",
    "terreno": "terreno",
    "estacionamiento": "estacionamiento",
    "bodega": "bodega",
}

# Comunas mapped to their portal inmobiliario URL slug (comuna-region)
COMUNAS_MAP = {
    # Región Metropolitana
    "santiago": "santiago-metropolitana",
    "providencia": "providencia-metropolitana",
    "las condes": "las-condes-metropolitana",
    "vitacura": "vitacura-metropolitana",
    "lo barnechea": "lo-barnechea-metropolitana",
    "nunoa": "nunoa-metropolitana",
    "ñuñoa": "nunoa-metropolitana",
    "la reina": "la-reina-metropolitana",
    "macul": "macul-metropolitana",
    "penalolen": "penalolen-metropolitana",
    "peñalolén": "penalolen-metropolitana",
    "la florida": "la-florida-metropolitana",
    "puente alto": "puente-alto-metropolitana",
    "maipu": "maipu-metropolitana",
    "maipú": "maipu-metropolitana",
    "estacion central": "estacion-central-metropolitana",
    "estación central": "estacion-central-metropolitana",
    "cerrillos": "cerrillos-metropolitana",
    "recoleta": "recoleta-metropolitana",
    "independencia": "independencia-metropolitana",
    "quilicura": "quilicura-metropolitana",
    "huechuraba": "huechuraba-metropolitana",
    "conchali": "conchali-metropolitana",
    "conchalí": "conchali-metropolitana",
    "renca": "renca-metropolitana",
    "san miguel": "san-miguel-metropolitana",
    "san joaquin": "san-joaquin-metropolitana",
    "san joaquín": "san-joaquin-metropolitana",
    "pedro aguirre cerda": "pedro-aguirre-cerda-metropolitana",
    "lo espejo": "lo-espejo-metropolitana",
    "la cisterna": "la-cisterna-metropolitana",
    "el bosque": "el-bosque-metropolitana",
    "san bernardo": "san-bernardo-metropolitana",
    "lo prado": "lo-prado-metropolitana",
    "cerro navia": "cerro-navia-metropolitana",
    "pudahuel": "pudahuel-metropolitana",
    "quinta normal": "quinta-normal-metropolitana",
    "la granja": "la-granja-metropolitana",
    "san ramon": "san-ramon-metropolitana",
    "san ramón": "san-ramon-metropolitana",
    "la pintana": "la-pintana-metropolitana",
    "colina": "colina-metropolitana",
    "lampa": "lampa-metropolitana",
    "chicureo": "chicureo-metropolitana",
    "buin": "buin-metropolitana",
    "paine": "paine-metropolitana",
    "talagante": "talagante-metropolitana",
    "peñaflor": "penaflor-metropolitana",
    "padre hurtado": "padre-hurtado-metropolitana",
    "isla de maipo": "isla-de-maipo-metropolitana",
    "melipilla": "melipilla-metropolitana",
    "san jose de maipo": "san-jose-de-maipo-metropolitana",
    # Valparaíso
    "valparaiso": "valparaiso-valparaiso",
    "valparaíso": "valparaiso-valparaiso",
    "viña del mar": "vina-del-mar-valparaiso",
    "vina del mar": "vina-del-mar-valparaiso",
    "concon": "concon-valparaiso",
    "concón": "concon-valparaiso",
    "quilpue": "quilpue-valparaiso",
    "quilpué": "quilpue-valparaiso",
    "villa alemana": "villa-alemana-valparaiso",
    "san antonio": "san-antonio-valparaiso",
    "quillota": "quillota-valparaiso",
    "la serena": "la-serena-coquimbo",
    "coquimbo": "coquimbo-coquimbo",
    # Biobío
    "concepcion": "concepcion-biobio",
    "concepción": "concepcion-biobio",
    "talcahuano": "talcahuano-biobio",
    "chillan": "chillan-nuble",
    "chillán": "chillan-nuble",
    # Araucanía
    "temuco": "temuco-araucania",
    # Los Lagos
    "puerto montt": "puerto-montt-los-lagos",
    "osorno": "osorno-los-lagos",
    # Antofagasta
    "antofagasta": "antofagasta-antofagasta",
    # Atacama
    "copiapo": "copiapo-atacama",
    "copiapó": "copiapo-atacama",
    # O'Higgins
    "rancagua": "rancagua-ohiggins",
    # Maule
    "talca": "talca-maule",
    # Los Ríos
    "valdivia": "valdivia-los-rios",
    # Aysén
    "coyhaique": "coyhaique-aysen",
    # Magallanes
    "punta arenas": "punta-arenas-magallanes",
    # Arica
    "arica": "arica-arica-y-parinacota",
    # Tarapacá
    "iquique": "iquique-tarapaca",
}

REGIONES_MAP = {
    "metropolitana": "rm-metropolitana",
    "valparaiso": "valparaiso",
    "biobio": "bio-bio",
    "araucania": "la-araucania",
    "los-lagos": "los-lagos",
    "coquimbo": "coquimbo",
    "ohiggins": "lib-gral-bernardo-o-higgins",
    "maule": "maule",
    "nuble": "nuble",
    "los-rios": "los-rios",
    "antofagasta": "antofagasta",
    "atacama": "atacama",
    "arica-y-parinacota": "arica-y-parinacota",
    "tarapaca": "tarapaca",
    "aysen": "aysen",
    "magallanes": "magallanes-y-la-antartica-chilena",
}


@dataclass
class PropertyData:
    url: str = ""
    titulo: str = ""
    precio_clp: str = ""
    precio_uf: str = ""
    ubicacion: str = ""
    region: str = ""
    comuna: str = ""
    barrio: str = ""
    tipo_propiedad: str = ""
    superficie_construida: str = ""
    superficie_total: str = ""
    habitaciones: str = ""
    banos: str = ""
    estacionamientos: str = ""
    bodegas: str = ""
    gastos_comunes: str = ""
    antiguedad: str = ""
    descripcion: str = ""
    fecha_publicacion: str = ""


@dataclass
class ScraperFilters:
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


def build_search_url(filters: ScraperFilters) -> str:
    op = OPERATION_MAP.get(filters.operacion, "venta")
    prop_type = PROPERTY_TYPE_MAP.get(filters.tipo_propiedad, "departamento")

    path = f"/{op}/{prop_type}"

    # Comuna takes priority over region (commune slug includes region)
    comuna_key = filters.comuna.strip().lower() if filters.comuna else ""
    if comuna_key and comuna_key in COMUNAS_MAP:
        path += f"/{COMUNAS_MAP[comuna_key]}"
    elif comuna_key:
        # Try to build slug: normalize and append region if available
        slug = comuna_key.replace(" ", "-").replace("ñ", "n").replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
        if filters.region:
            slug += f"-{filters.region}"
        path += f"/{slug}"
    elif filters.region:
        region_slug = REGIONES_MAP.get(filters.region, filters.region)
        path += f"/{region_slug}"

    params = []

    if filters.precio_min is not None:
        params.append(f"precio-desde_{filters.precio_min}")
    if filters.precio_max is not None:
        params.append(f"precio-hasta_{filters.precio_max}")
    if filters.superficie_min is not None:
        params.append(f"superficie-desde_{filters.superficie_min}")
    if filters.superficie_max is not None:
        params.append(f"superficie-hasta_{filters.superficie_max}")
    if filters.habitaciones is not None and filters.habitaciones > 0:
        params.append(f"{filters.habitaciones}-dormitorios")
    if filters.banos is not None and filters.banos > 0:
        params.append(f"{filters.banos}-banos")
    if filters.estacionamiento:
        params.append("con-estacionamiento")
    if filters.bodega:
        params.append("con-bodega")
    if filters.amoblado:
        params.append("amoblado")

    if params:
        path += "/" + "_".join(params)

    return BASE_URL + path


def validate_portal_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.hostname in (
        "www.portalinmobiliario.com",
        "portalinmobiliario.com",
    )


INIT_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
    Object.defineProperty(navigator, 'languages', {get: () => ['es-CL', 'es', 'en']});
    window.chrome = { runtime: {}, loadTimes: () => ({}), csi: () => ({}) };
    Object.defineProperty(navigator, 'maxTouchPoints', {get: () => 1});
    Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
    Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
    Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) =>
        parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters);
"""


class PortalScraper:
    CONCURRENT_TABS = 4  # Number of parallel detail page fetches

    def __init__(self, on_progress: Optional[Callable[[dict], Awaitable[None]]] = None):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.properties: list[PropertyData] = []
        self.on_progress = on_progress
        self._cancelled = False
        self._pw = None

    async def _emit(self, data: dict):
        if self.on_progress:
            await self.on_progress(data)

    def cancel(self):
        self._cancelled = True

    async def start_browser(self):
        self._pw = await async_playwright().start()
        self.browser = await self._pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        self.context = await self.browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="es-CL",
            timezone_id="America/Santiago",
            geolocation={"latitude": -33.4489, "longitude": -70.6693},
            permissions=["geolocation"],
        )
        await self.context.add_init_script(INIT_SCRIPT)
        self.page = await self.context.new_page()

    async def close_browser(self):
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self._pw:
            await self._pw.stop()
            self._pw = None

    async def _navigate(self, page: Page, url: str, wait_selector: str = "", retries: int = 3) -> str:
        """Navigate, handle verification challenges, and wait smartly."""
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)

        # Handle MercadoLibre account-verification challenge
        for attempt in range(retries):
            current_url = page.url
            if "/gz/account-verification" not in current_url and "/gz/challenge" not in current_url:
                break

            await self._emit({
                "type": "info",
                "message": f"Challenge de verificación detectado (intento {attempt + 1}/{retries}). Esperando resolución...",
            })

            # Wait for the JS challenge to resolve and redirect back
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
                await page.wait_for_url(
                    lambda u: "/gz/account-verification" not in u and "/gz/challenge" not in u,
                    timeout=30000,
                )
            except Exception:
                # Challenge didn't resolve, retry navigation
                if attempt < retries - 1:
                    await asyncio.sleep(3)
                    await page.goto(url, wait_until="domcontentloaded", timeout=45000)

        if wait_selector:
            try:
                await page.wait_for_selector(wait_selector, timeout=15000)
            except Exception:
                try:
                    await page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass
        else:
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
        return await page.content()

    async def extract_cards_from_search(self, page: Page) -> list[PropertyData]:
        """Extract property data directly from search results cards - no detail page visit needed."""
        results = await page.evaluate("""
            () => {
                const items = [];
                // Search result items
                const cards = document.querySelectorAll('.ui-search-layout__item');
                cards.forEach(card => {
                    const item = {};

                    // URL
                    const link = card.querySelector('a[href*="/MLC-"]');
                    item.url = link ? link.href.split('#')[0].split('?')[0] : '';

                    // Title
                    const title = card.querySelector(
                        '.ui-search-item__title, ' +
                        '.ui-search-item__group__element .ui-search-item__title, ' +
                        'h2'
                    );
                    item.titulo = title ? title.textContent.trim() : '';

                    // Prices - get all price elements
                    item.precio_clp = '';
                    item.precio_uf = '';
                    const priceEls = card.querySelectorAll(
                        '.andes-money-amount, .price-tag-amount, .ui-search-price__second-line .andes-money-amount'
                    );
                    priceEls.forEach(el => {
                        const txt = el.textContent.trim();
                        if (txt.includes('UF')) {
                            item.precio_uf = txt;
                        } else if (txt.includes('$') || txt.match(/\\d/)) {
                            if (!item.precio_clp) item.precio_clp = txt;
                        }
                    });
                    // Fallback price
                    if (!item.precio_clp && !item.precio_uf) {
                        const priceContainer = card.querySelector('.ui-search-price, .price-tag');
                        if (priceContainer) {
                            item.precio_clp = priceContainer.textContent.trim().split('\\n')[0];
                        }
                    }

                    // Location
                    const loc = card.querySelector(
                        '.ui-search-item__location, ' +
                        '.ui-search-item__group__element--location, ' +
                        '.ui-search-item__subtitle'
                    );
                    item.ubicacion = loc ? loc.textContent.trim() : '';

                    // Attributes (rooms, bathrooms, area) from card tags
                    item.habitaciones = '';
                    item.banos = '';
                    item.superficie_construida = '';
                    item.superficie_total = '';
                    item.estacionamientos = '';
                    item.bodegas = '';

                    const attrs = card.querySelectorAll(
                        '.ui-search-card-attributes__attribute, ' +
                        '.ui-search-item__attributes li, ' +
                        '.ui-search-card-attributes li'
                    );
                    attrs.forEach(attr => {
                        const text = attr.textContent.trim().toLowerCase();
                        if (text.includes('dorm') || text.includes('hab')) {
                            const m = text.match(/(\\d+)/);
                            if (m) item.habitaciones = m[1];
                        } else if (text.includes('bañ') || text.includes('ban')) {
                            const m = text.match(/(\\d+)/);
                            if (m) item.banos = m[1];
                        } else if (text.includes('m²') || text.includes('m2')) {
                            const m = text.match(/([\\d.,]+)/);
                            if (m) {
                                if (text.includes('total') || text.includes('terreno')) {
                                    item.superficie_total = m[1] + ' m²';
                                } else {
                                    item.superficie_construida = m[1] + ' m²';
                                }
                            }
                        } else if (text.includes('estac')) {
                            const m = text.match(/(\\d+)/);
                            if (m) item.estacionamientos = m[1];
                        } else if (text.includes('bodega')) {
                            const m = text.match(/(\\d+)/);
                            if (m) item.bodegas = m[1];
                        }
                    });

                    if (item.url) items.push(item);
                });
                return items;
            }
        """)

        properties = []
        for r in results:
            prop = PropertyData(
                url=r.get("url", ""),
                titulo=r.get("titulo", ""),
                precio_clp=r.get("precio_clp", ""),
                precio_uf=r.get("precio_uf", ""),
                ubicacion=r.get("ubicacion", ""),
                habitaciones=r.get("habitaciones", ""),
                banos=r.get("banos", ""),
                superficie_construida=r.get("superficie_construida", ""),
                superficie_total=r.get("superficie_total", ""),
                estacionamientos=r.get("estacionamientos", ""),
                bodegas=r.get("bodegas", ""),
            )
            # Parse location into parts
            if prop.ubicacion:
                parts = [p.strip() for p in prop.ubicacion.split(",")]
                if len(parts) >= 3:
                    prop.barrio = parts[0]
                    prop.comuna = parts[-2]
                    prop.region = parts[-1]
                elif len(parts) == 2:
                    prop.comuna = parts[0]
                    prop.region = parts[1]
                elif len(parts) == 1:
                    prop.comuna = parts[0]
            properties.append(prop)

        return properties

    async def get_total_results(self, page: Page) -> int:
        try:
            count = await page.evaluate("""
                () => {
                    const el = document.querySelector('.ui-search-search-result__quantity-results');
                    if (el) {
                        const m = el.textContent.replace(/\\./g, '').match(/\\d+/);
                        return m ? parseInt(m[0]) : 0;
                    }
                    return 0;
                }
            """)
            return count or 0
        except Exception:
            return 0

    async def get_next_page_url(self, page: Page) -> Optional[str]:
        try:
            return await page.evaluate("""
                () => {
                    const next = document.querySelector(
                        'a.andes-pagination__link[title="Siguiente"], ' +
                        'li.andes-pagination__button--next a'
                    );
                    return next ? next.href : null;
                }
            """)
        except Exception:
            return None

    async def extract_detail(self, prop: PropertyData) -> PropertyData:
        """Visit detail page in a new tab to get extra fields (description, gastos comunes, etc)."""
        detail_page = await self.context.new_page()
        try:
            await self._navigate(
                detail_page, prop.url,
                wait_selector=".ui-pdp-container, .ui-pdp-title, .ui-vip-core"
            )

            data = await detail_page.evaluate("""
                () => {
                    const getText = (sel) => {
                        const el = document.querySelector(sel);
                        return el ? el.textContent.trim() : '';
                    };

                    // Prices (more precise from detail)
                    let precioCLP = '';
                    let precioUF = '';
                    const priceEls = document.querySelectorAll('.ui-pdp-price .andes-money-amount');
                    priceEls.forEach(el => {
                        const t = el.textContent.trim();
                        if (t.includes('UF')) precioUF = t;
                        else if (t.includes('$')) precioCLP = t;
                    });
                    if (!precioCLP) precioCLP = getText('.ui-pdp-price__second-line .andes-money-amount');

                    const titulo = getText('.ui-pdp-title') || getText('h1');
                    const ubicacion = getText('.ui-pdp-media__title');
                    const descripcion = getText('.ui-pdp-description__content') || getText('.ui-pdp-description p');
                    let fechaPub = getText('.ui-pdp-header__bottom-subtitle');

                    // Specs/attrs table
                    const attrs = {};
                    document.querySelectorAll('.andes-table__row, .ui-pdp-specs__table__row, .ui-pdp-specs__table tr').forEach(row => {
                        const header = row.querySelector('th, .andes-table__header__container');
                        const value = row.querySelector('td, .andes-table__column__container');
                        if (header && value) {
                            attrs[header.textContent.trim().toLowerCase()] = value.textContent.trim();
                        }
                    });

                    // Highlighted specs
                    document.querySelectorAll('.ui-pdp-highlighted-specs-res__icon-label, .ui-pdp-features__item').forEach(el => {
                        const text = el.textContent.trim().toLowerCase();
                        if (text.includes('dormitorio')) {
                            const m = text.match(/(\\d+)/);
                            if (m) attrs['_dormitorios'] = m[1];
                        }
                        if (text.includes('baño')) {
                            const m = text.match(/(\\d+)/);
                            if (m) attrs['_banos'] = m[1];
                        }
                        if (text.includes('m²') || text.includes('m2')) {
                            attrs['_superficie'] = text;
                        }
                    });

                    // Gastos comunes
                    let gastos = '';
                    document.querySelectorAll('.ui-pdp-media__body p, .ui-pdp-specs__table td, span').forEach(el => {
                        if (el.textContent.toLowerCase().includes('gastos comunes')) {
                            gastos = el.textContent.trim();
                        }
                    });

                    return {
                        titulo, precioCLP, precioUF, ubicacion,
                        descripcion, fechaPub, gastos, attrs
                    };
                }
            """)

            # Merge detail data into property (don't overwrite card data with empty strings)
            if data.get("titulo"):
                prop.titulo = data["titulo"]
            if data.get("precioCLP"):
                prop.precio_clp = data["precioCLP"]
            if data.get("precioUF"):
                prop.precio_uf = data["precioUF"]
            if data.get("ubicacion"):
                prop.ubicacion = data["ubicacion"]
            prop.descripcion = data.get("descripcion", "")
            prop.fecha_publicacion = data.get("fechaPub", "")
            prop.gastos_comunes = data.get("gastos", "")

            attrs = data.get("attrs", {})
            for key, val in attrs.items():
                if key.startswith("_"):
                    continue
                kl = key.lower()
                if "superficie construida" in kl or "superficie útil" in kl:
                    prop.superficie_construida = val
                elif "superficie total" in kl or "superficie terreno" in kl:
                    prop.superficie_total = val
                elif "dormitorio" in kl:
                    prop.habitaciones = val
                elif "baño" in kl:
                    prop.banos = val
                elif "estacionamiento" in kl:
                    prop.estacionamientos = val
                elif "bodega" in kl:
                    prop.bodegas = val
                elif "antigüedad" in kl or "antiguedad" in kl or "año de construcción" in kl:
                    prop.antiguedad = val
                elif "tipo de propiedad" in kl or "inmueble" in kl:
                    prop.tipo_propiedad = val
                elif "gastos comunes" in kl:
                    prop.gastos_comunes = val

            # Fill from highlighted if card didn't have it
            if not prop.habitaciones and attrs.get("_dormitorios"):
                prop.habitaciones = attrs["_dormitorios"]
            if not prop.banos and attrs.get("_banos"):
                prop.banos = attrs["_banos"]

            # Parse location
            if prop.ubicacion and not prop.comuna:
                parts = [p.strip() for p in prop.ubicacion.split(",")]
                if len(parts) >= 3:
                    prop.barrio = parts[0]
                    prop.comuna = parts[-2]
                    prop.region = parts[-1]
                elif len(parts) == 2:
                    prop.comuna = parts[0]
                    prop.region = parts[1]

        except Exception as e:
            await self._emit({"type": "warning", "message": f"Error en detalle {prop.url}: {e}"})
        finally:
            await detail_page.close()

        return prop

    async def _extract_details_batch(self, props: list[PropertyData], start_idx: int, total: int) -> list[PropertyData]:
        """Extract details for a batch of properties concurrently."""
        tasks = []
        for prop in props:
            if self._cancelled:
                break
            tasks.append(self.extract_detail(prop))

        results = []
        for i, coro in enumerate(asyncio.as_completed(tasks)):
            prop = await coro
            results.append(prop)
            idx = start_idx + i + 1
            progress = 30 + int((idx / total) * 70)
            await self._emit({
                "type": "progress",
                "message": f"Detalle propiedad {idx}/{total}",
                "progress": progress,
                "current": idx,
                "total": total,
            })
            await self._emit({
                "type": "property",
                "data": asdict(prop),
                "index": idx,
                "total": total,
            })

        return results

    async def scrape(
        self,
        url: str,
        max_pages: int = 10,
        max_properties: int = 100,
    ) -> list[PropertyData]:
        self.properties = []
        self._cancelled = False

        await self.start_browser()

        try:
            await self._emit({
                "type": "status",
                "message": "Navegando a la página de búsqueda...",
                "progress": 0,
            })

            current_url = url
            page_num = 1
            all_properties: list[PropertyData] = []

            # Phase 1: Collect data from search result cards (fast)
            while page_num <= max_pages and len(all_properties) < max_properties:
                if self._cancelled:
                    await self._emit({"type": "cancelled", "message": "Scraping cancelado"})
                    break

                await self._emit({
                    "type": "status",
                    "message": f"Escaneando página {page_num}...",
                    "progress": int((page_num / max_pages) * 30),
                    "page": page_num,
                })

                await self._navigate(
                    self.page, current_url,
                    wait_selector="ol.ui-search-layout, .ui-search-results"
                )

                # Diagnóstico: reportar título y URL final de la página
                page_title = await self.page.title()
                page_url = self.page.url
                await self._emit({
                    "type": "info",
                    "message": f"Página cargada - Título: '{page_title}' | URL: {page_url}",
                })

                # Detectar bloqueos comunes (CAPTCHA, challenge, access denied)
                body_text = await self.page.evaluate("() => document.body?.innerText?.substring(0, 500) || ''")
                blocked_signals = ["captcha", "challenge", "blocked", "access denied", "robot", "verificar"]
                if any(sig in body_text.lower() for sig in blocked_signals):
                    await self._emit({
                        "type": "warning",
                        "message": f"Posible bloqueo detectado. Contenido de la página: {body_text[:300]}",
                    })

                if page_num == 1:
                    total = await self.get_total_results(self.page)
                    await self._emit({
                        "type": "info",
                        "message": f"Total de resultados encontrados: {total}",
                        "total_results": total,
                    })

                card_props = await self.extract_cards_from_search(self.page)

                if not card_props:
                    await self._emit({
                        "type": "warning",
                        "message": f"No se encontraron propiedades en página {page_num}",
                    })
                    break

                all_properties.extend(card_props)
                await self._emit({
                    "type": "info",
                    "message": f"Extraídas {len(card_props)} propiedades de página {page_num}. Total: {len(all_properties)}",
                })

                if len(all_properties) >= max_properties:
                    all_properties = all_properties[:max_properties]
                    break

                next_url = await self.get_next_page_url(self.page)
                if not next_url:
                    break

                current_url = next_url
                page_num += 1
                await asyncio.sleep(1)

            # Phase 2: Extract details concurrently in batches
            total_to_process = len(all_properties)
            await self._emit({
                "type": "status",
                "message": f"Extrayendo detalles de {total_to_process} propiedades ({self.CONCURRENT_TABS} en paralelo)...",
                "progress": 30,
                "total_properties": total_to_process,
            })

            processed = 0
            for batch_start in range(0, total_to_process, self.CONCURRENT_TABS):
                if self._cancelled:
                    await self._emit({"type": "cancelled", "message": "Scraping cancelado"})
                    break

                batch = all_properties[batch_start:batch_start + self.CONCURRENT_TABS]
                detailed = await self._extract_details_batch(batch, processed, total_to_process)
                self.properties.extend(detailed)
                processed += len(detailed)

                # Small pause between batches to avoid rate limiting
                if processed < total_to_process:
                    await asyncio.sleep(1.5)

            await self._emit({
                "type": "complete",
                "message": f"Scraping completado. {len(self.properties)} propiedades extraídas.",
                "progress": 100,
                "total_extracted": len(self.properties),
            })

        except Exception as e:
            await self._emit({
                "type": "error",
                "message": f"Error durante el scraping: {str(e)}",
            })
        finally:
            await self.close_browser()

        return self.properties


def properties_to_csv(properties: list[PropertyData]) -> str:
    if not properties:
        return ""

    output = io.StringIO()
    fieldnames = [
        "URL", "Título", "Precio CLP", "Precio UF", "Ubicación",
        "Región", "Comuna", "Barrio", "Tipo Propiedad",
        "Superficie Construida", "Superficie Total",
        "Habitaciones", "Baños", "Estacionamientos", "Bodegas",
        "Gastos Comunes", "Antigüedad", "Fecha Publicación",
    ]

    writer = csv.DictWriter(output, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
    writer.writeheader()

    for prop in properties:
        writer.writerow({
            "URL": prop.url,
            "Título": prop.titulo,
            "Precio CLP": prop.precio_clp,
            "Precio UF": prop.precio_uf,
            "Ubicación": prop.ubicacion,
            "Región": prop.region,
            "Comuna": prop.comuna,
            "Barrio": prop.barrio,
            "Tipo Propiedad": prop.tipo_propiedad,
            "Superficie Construida": prop.superficie_construida,
            "Superficie Total": prop.superficie_total,
            "Habitaciones": prop.habitaciones,
            "Baños": prop.banos,
            "Estacionamientos": prop.estacionamientos,
            "Bodegas": prop.bodegas,
            "Gastos Comunes": prop.gastos_comunes,
            "Antigüedad": prop.antiguedad,
            "Fecha Publicación": prop.fecha_publicacion,
        })

    return output.getvalue()
