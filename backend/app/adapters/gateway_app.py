"""Internal HTTP gateway for durable simulated devices; no public unauthenticated writes."""
import hmac
import os

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.adapters.persistent_gateway import PersistentVirtualGateway
from app.adapters.protocol import DeviceCommandRequest
from app.adapters.virtual.devices import CAPABILITIES
from app.demo import seed


class FenceRequest(BaseModel):
    epoch: int = Field(ge=0)


def create_app(path=None, token=None):
    token = token or os.getenv("LIVINGMIND_GATEWAY_TOKEN", "")
    if not token:
        raise RuntimeError("LIVINGMIND_GATEWAY_TOKEN is required for the internal gateway")
    gateway = PersistentVirtualGateway(path or os.getenv("LIVINGMIND_GATEWAY_DATA", "/data/gateway.sqlite3"),
                                       {s.space_id: seed.INITIAL_DEVICE_STATE for s in seed.SPACES})

    def authorized(authorization: str = Header(default="")):
        if not hmac.compare_digest(authorization, f"Bearer {token}"):
            raise HTTPException(401, "gateway authorization required")

    app = FastAPI(title="LivingMind internal virtual gateway", dependencies=[Depends(authorized)])

    @app.get("/health")
    def health():
        return {"status": "ok", "device_source": "persistent_virtual"}

    @app.get("/spaces/{space_id}/state")
    def state(space_id: str):
        try:
            return gateway.state(space_id)
        except KeyError:
            raise HTTPException(404, "unknown space")

    @app.get("/spaces/{space_id}/capabilities")
    def capabilities(space_id: str):
        if space_id not in gateway.initial:
            raise HTTPException(404, "unknown space")
        return CAPABILITIES

    @app.post("/spaces/{space_id}/fence")
    def fence(space_id: str, body: FenceRequest):
        try:
            gateway.fence(space_id, body.epoch)
            return {"ok": True}
        except KeyError:
            raise HTTPException(404, "unknown space")

    @app.post("/spaces/{space_id}/reset")
    def reset(space_id: str, body: FenceRequest):
        try:
            return {"reset": gateway.reset(space_id, body.epoch)}
        except KeyError:
            raise HTTPException(404, "unknown space")

    @app.post("/commands")
    def submit(body: DeviceCommandRequest):
        return gateway.submit(body)

    @app.get("/commands/{action_id}")
    def query(action_id: str):
        return gateway.query(action_id)

    return app
