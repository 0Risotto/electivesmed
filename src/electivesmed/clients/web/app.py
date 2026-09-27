"""FastAPI app factory for the local web UI."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from ...components.security import LoginThrottle
from ...di.providers import provide_container
from .deps import AuthRequired, check_origin, redirect_to_login, require_user
from .routes import (
    auth,
    campaigns,
    compliance,
    contacts,
    dashboard,
    documents,
    drafts,
    sending,
)
from .routes import settings as settings_routes
from .routes import sources
from .runner import BackgroundRunner

STATIC_DIR = Path(__file__).parent / "static"


def create_app(container=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.container = container if container is not None else provide_container()
        settings = app.state.container.settings
        app.state.runner = BackgroundRunner()
        app.state.login_throttle = LoginThrottle(
            limit=settings.web.login_attempts,
            window=settings.web.lockout_seconds,
        )
        try:
            yield
        finally:
            app.state.runner.shutdown()
            if container is None:
                app.state.container.close()

    app = FastAPI(title="electivesmed", lifespan=lifespan)

    @app.exception_handler(AuthRequired)
    async def _auth_required(request, exc):  # pragma: no cover - trivial branch
        if request.app.state.container.dao.count_users() == 0:
            return RedirectResponse("/setup", status_code=303)
        return redirect_to_login(request)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(auth.router)
    protected = [Depends(require_user), Depends(check_origin)]
    for router in (
        dashboard.router,
        contacts.router,
        drafts.router,
        campaigns.router,
        sending.router,
        sources.router,
        compliance.router,
        documents.router,
        settings_routes.router,
    ):
        app.include_router(router, dependencies=protected)
    return app
