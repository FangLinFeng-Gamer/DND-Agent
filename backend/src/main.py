from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.src.api.adventures import router as adventures_router
from backend.src.api.assets import router as assets_router
from backend.src.api.character_creation import router as character_creation_router
from backend.src.api.characters import router as characters_router
from backend.src.api.maps import router as maps_router
from backend.src.api.models import router as models_router
from backend.src.api.stories import router as stories_router
from backend.src.api.system import router as system_router
from backend.src.api.world import router as world_router
from backend.src.core.settings import DEFAULT_DB_PATH, DEFAULT_STATIC_DIR
from backend.src.db.sqlite import SQLiteStore
from backend.src.services.stories import StoryService
from backend.src.services.world import WorldService


FRONTEND_ROUTES = (
    "/home",
    "/races",
    "/character-create",
    "/stories",
    "/game",
    "/play",
    "/models",
)
FRONTEND_DYNAMIC_ROUTES = (
    "/game/{adventure_id:int}",
)


def initialize_store(store: SQLiteStore) -> None:
    store.init_schema()
    WorldService(store).seed_defaults()
    StoryService(store).seed_defaults()


def create_app(db_path: str | Path | None = None, static_dir: str | Path | None = DEFAULT_STATIC_DIR) -> FastAPI:
    store = SQLiteStore(db_path or DEFAULT_DB_PATH)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        initialize_store(store)
        yield

    app = FastAPI(title="DND-Agent", root_path="/dnd-agent/v1", lifespan=lifespan)
    app.state.store = store

    @app.middleware("http")
    async def ensure_store_schema(request, call_next):
        if request.url.path.startswith("/api/"):
            initialize_store(store)
        return await call_next(request)

    app.include_router(characters_router)
    app.include_router(character_creation_router)
    app.include_router(models_router)
    app.include_router(stories_router)
    app.include_router(world_router)
    app.include_router(adventures_router)
    app.include_router(maps_router)
    app.include_router(assets_router)
    app.include_router(system_router)

    if static_dir:
        static_path = Path(static_dir)
        if static_path.exists():
            register_frontend_routes(app, static_path)
            app.mount("/", StaticFiles(directory=static_path, html=True), name="static")

    return app


def register_frontend_routes(app: FastAPI, static_path: Path) -> None:
    index_path = static_path / "index.html"

    async def redirect_to_home():
        return RedirectResponse(url="/home")

    async def spa_index():
        return FileResponse(index_path)

    app.add_api_route("/", redirect_to_home, methods=["GET"], include_in_schema=False)
    if app.root_path:
        app.add_api_route(
            app.root_path,
            lambda: RedirectResponse(url=f"{app.root_path}/home"),
            methods=["GET"],
            include_in_schema=False,
        )

    prefixes = ("", app.root_path) if app.root_path else ("",)
    for prefix in prefixes:
        for route in FRONTEND_ROUTES:
            app.add_api_route(
                f"{prefix}{route}",
                spa_index,
                methods=["GET"],
                include_in_schema=False,
            )
        for route in FRONTEND_DYNAMIC_ROUTES:
            app.add_api_route(
                f"{prefix}{route}",
                spa_index,
                methods=["GET"],
                include_in_schema=False,
            )


app = create_app()


if __name__ == "__main__":
    uvicorn.run("backend.src.main:app", port=5000, log_level="info")
