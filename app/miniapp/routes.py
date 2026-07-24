"""HTTP + WebSocket routes for the Mini App.

REST endpoints are used for one-shot reads/actions; the WebSocket endpoint
(``/ws/{game_id}``) carries the realtime stream: server-pushed table snapshots
plus a peer-to-peer WebRTC signaling relay (``rtc.*`` messages) for voice.

Every route authenticates via verified ``initData`` (see :mod:`app.miniapp.deps`)
and every mutation re-publishes a fresh snapshot to the whole room so all clients
converge without polling.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Path, WebSocket
from fastapi.responses import JSONResponse
from starlette.websockets import WebSocketDisconnect

from app.config.logging import get_logger
from app.config.settings import get_settings
from app.miniapp.auth import InitDataError, verify_init_data
from app.miniapp.config import get_miniapp_config
from app.miniapp.deps import (
    ConfigDep,
    ServiceDep,
    UserIdDep,
    get_hub,
)
from app.miniapp.live_state import Phase
from app.miniapp.realtime import RealtimeHub
from app.miniapp.service import MiniAppService, TableSnapshot
from app.services import ServiceProvider
from app.utils.exceptions import DomainError

logger = get_logger(__name__)

router = APIRouter()


def _snapshot_payload(snap: TableSnapshot) -> dict[str, Any]:
    """Serialize a :class:`TableSnapshot` to a JSON-safe dict."""
    return {
        "type": "table",
        "game_id": snap.game_id,
        "code": snap.code,
        "scenario_code": snap.scenario_code,
        "status": snap.status,
        "player_count": snap.player_count,
        "is_creator": snap.is_creator,
        "seats": [asdict(s) for s in snap.seats],
        "live": snap.live,
        "vote_tally": snap.vote_tally,
    }


async def _publish_invalidate(hub: RealtimeHub, game_id: int) -> None:
    """Nudge every client in the room to refetch its own table snapshot.

    We deliberately broadcast only an ``invalidate`` marker rather than a full
    table payload: each viewer's snapshot embeds a per-player secret (their own
    role), so clients pull their personalized view over the authenticated REST
    endpoint instead of receiving someone else's.
    """
    await hub.publish(game_id, {"type": "invalidate", "game_id": game_id})


# --- REST ------------------------------------------------------------------


@router.get("/api/health")
async def health() -> dict[str, str]:
    """Liveness probe (no auth)."""
    return {"status": "ok"}


@router.get("/api/games/{game_id}")
async def get_table(
    game_id: Annotated[int, Path(ge=1)],
    user_id: UserIdDep,
    service: ServiceDep,
) -> JSONResponse:
    """Return the caller's view of a table (membership-checked)."""
    snap = await service.get_snapshot(game_id=game_id, user_id=user_id)
    return JSONResponse(_snapshot_payload(snap))


@router.post("/api/games/join")
async def join_by_code(
    user_id: UserIdDep,
    service: ServiceDep,
    code: Annotated[str, Body(embed=True, min_length=6, max_length=6)],
) -> JSONResponse:
    """Resolve a 6-digit code to a game the caller already belongs to.

    Actual lobby joining/seat selection remains owned by the bot flow; the Mini
    App is the live *table*, so here we only resolve the code and verify
    membership, returning the initial snapshot.
    """
    game = await service.game_by_code(code)
    if game is None:
        raise HTTPException(status_code=404, detail="بازی با این کد پیدا نشد.")
    snap = await service.get_snapshot(game_id=game.id, user_id=user_id)
    return JSONResponse(_snapshot_payload(snap))


# --- Player actions --------------------------------------------------------


@router.post("/api/games/{game_id}/vote")
async def vote(
    game_id: Annotated[int, Path(ge=1)],
    user_id: UserIdDep,
    service: ServiceDep,
    hub: Annotated[RealtimeHub, Depends(get_hub)],
    target: Annotated[int, Body(embed=True, ge=1)],
) -> JSONResponse:
    """Cast (or overwrite) this player's secret vote during the voting phase."""
    live = await service.cast_vote(
        game_id=game_id, user_id=user_id, target_number=target
    )
    await service.save(game_id, live)
    await _publish_invalidate(hub, game_id)
    return JSONResponse({"ok": True, "version": live.version})


@router.post("/api/games/{game_id}/challenge")
async def challenge(
    game_id: Annotated[int, Path(ge=1)],
    user_id: UserIdDep,
    service: ServiceDep,
    hub: Annotated[RealtimeHub, Depends(get_hub)],
    config: ConfigDep,
    target: Annotated[int, Body(embed=True, ge=1)],
) -> JSONResponse:
    """Current speaker declares a challenge against another seat (once/turn)."""
    live = await service.declare_challenge(
        game_id=game_id,
        user_id=user_id,
        target_number=target,
        seconds=config.challenge_seconds,
    )
    await service.save(game_id, live)
    await _publish_invalidate(hub, game_id)
    return JSONResponse({"ok": True, "version": live.version})


# --- Manager (creator-only) actions ----------------------------------------


@router.post("/api/games/{game_id}/manager/phase")
async def set_phase(
    game_id: Annotated[int, Path(ge=1)],
    user_id: UserIdDep,
    service: ServiceDep,
    hub: Annotated[RealtimeHub, Depends(get_hub)],
    config: ConfigDep,
    phase: Annotated[str, Body(embed=True)],
) -> JSONResponse:
    """Creator moves the table to a new phase (lobby/day/night/voting/...)."""
    try:
        phase_enum = Phase(phase)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="فاز نامعتبر است.") from exc
    live = await service.set_phase(
        game_id=game_id,
        user_id=user_id,
        phase=phase_enum,
        speaking_seconds=config.speaking_seconds,
    )
    await service.save(game_id, live)
    await _publish_invalidate(hub, game_id)
    return JSONResponse({"ok": True, "version": live.version})


@router.post("/api/games/{game_id}/manager/turn")
async def start_turn(
    game_id: Annotated[int, Path(ge=1)],
    user_id: UserIdDep,
    service: ServiceDep,
    hub: Annotated[RealtimeHub, Depends(get_hub)],
    config: ConfigDep,
    number: Annotated[int, Body(embed=True, ge=1)],
) -> JSONResponse:
    """Creator gives the speaking floor to a seat and arms the timer."""
    live = await service.start_turn(
        game_id=game_id,
        user_id=user_id,
        number=number,
        seconds=config.speaking_seconds,
    )
    await service.save(game_id, live)
    # Mark this table 'hot' so the server timer loop counts it down.
    hub_request_app_hot(hub).add(game_id)
    await _publish_invalidate(hub, game_id)
    return JSONResponse({"ok": True, "version": live.version})


@router.post("/api/games/{game_id}/manager/timer")
async def timer(
    game_id: Annotated[int, Path(ge=1)],
    user_id: UserIdDep,
    service: ServiceDep,
    hub: Annotated[RealtimeHub, Depends(get_hub)],
    running: Annotated[bool, Body(embed=True)],
) -> JSONResponse:
    """Creator pauses/resumes the current speaking timer."""
    live = await service.set_timer(game_id=game_id, user_id=user_id, running=running)
    await service.save(game_id, live)
    if running:
        hub_request_app_hot(hub).add(game_id)
    await _publish_invalidate(hub, game_id)
    return JSONResponse({"ok": True, "version": live.version})


@router.post("/api/games/{game_id}/manager/time")
async def adjust_time(
    game_id: Annotated[int, Path(ge=1)],
    user_id: UserIdDep,
    service: ServiceDep,
    hub: Annotated[RealtimeHub, Depends(get_hub)],
    delta: Annotated[int, Body(embed=True)],
) -> JSONResponse:
    """Creator adds/removes speaking seconds on the fly."""
    live = await service.adjust_time(game_id=game_id, user_id=user_id, delta=delta)
    await service.save(game_id, live)
    await _publish_invalidate(hub, game_id)
    return JSONResponse({"ok": True, "version": live.version})


@router.post("/api/games/{game_id}/manager/mute-all")
async def mute_all(
    game_id: Annotated[int, Path(ge=1)],
    user_id: UserIdDep,
    service: ServiceDep,
    hub: Annotated[RealtimeHub, Depends(get_hub)],
) -> JSONResponse:
    """Creator force-mutes everyone (e.g. between turns)."""
    live = await service.mute_all(game_id=game_id, user_id=user_id)
    await service.save(game_id, live)
    await _publish_invalidate(hub, game_id)
    return JSONResponse({"ok": True, "version": live.version})


@router.post("/api/games/{game_id}/manager/eliminate")
async def eliminate(
    game_id: Annotated[int, Path(ge=1)],
    user_id: UserIdDep,
    service: ServiceDep,
    hub: Annotated[RealtimeHub, Depends(get_hub)],
    number: Annotated[int, Body(embed=True, ge=1)],
) -> JSONResponse:
    """Creator eliminates a seat (persists the player as LEFT)."""
    await service.eliminate(game_id=game_id, user_id=user_id, number=number)
    await _publish_invalidate(hub, game_id)
    return JSONResponse({"ok": True})


def hub_request_app_hot(hub: RealtimeHub) -> set[int]:
    """Return the shared 'hot games' set the timer loop watches.

    The set lives on ``app.state`` (created in the lifespan); the hub holds a
    back-reference so route handlers can mark a table active without importing
    the app object.
    """
    return hub.hot_games


# --- WebSocket -------------------------------------------------------------


@router.websocket("/ws/{game_id}")
async def table_ws(websocket: WebSocket, game_id: int) -> None:
    """Realtime table stream + WebRTC signaling relay.

    Handshake: the client sends its ``initData`` as the first text frame (query
    params can't carry it safely). We verify it, confirm membership, then join
    the room. Thereafter:

    * server -> client: ``{"type": "invalidate"}`` nudges (client refetches the
      REST snapshot) and relayed ``rtc.*`` signaling frames;
    * client -> server: ``rtc.*`` frames (SDP offer/answer, ICE) which we
      rebroadcast to the room so peers can establish voice directly.
    """
    app = websocket.app
    settings = get_settings()
    config = get_miniapp_config()
    hub: RealtimeHub = app.state.hub
    session_factory = app.state.session_factory
    live_store = app.state.live_store

    await websocket.accept()

    # --- Authenticated handshake ---
    try:
        first = await websocket.receive_text()
    except WebSocketDisconnect:
        return
    try:
        init = verify_init_data(
            first,
            bot_token=settings.bot_token,
            max_age_seconds=config.miniapp_initdata_ttl,
        )
    except InitDataError:
        await websocket.close(code=4401)  # unauthorized
        return

    user_id = init.user.id
    async with session_factory() as session:
        service = MiniAppService(ServiceProvider(session), live_store)
        try:
            await service.ensure_member(game_id=game_id, user_id=user_id)
            snap = await service.get_snapshot(game_id=game_id, user_id=user_id)
        except DomainError:
            await websocket.close(code=4403)  # forbidden / not a member
            return
        await websocket.send_json(_snapshot_payload(snap))

    await hub.join(game_id, websocket)
    try:
        while True:
            msg = await websocket.receive_json()
            kind = msg.get("type", "")
            if kind.startswith("rtc."):
                # Relay WebRTC signaling verbatim to the rest of the room. We
                # stamp the sender so peers can route answers/ICE correctly.
                msg["from_user_id"] = user_id
                await hub.publish(game_id, msg)
    except WebSocketDisconnect:
        pass
    finally:
        await hub.leave(game_id, websocket)
