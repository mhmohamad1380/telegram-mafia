"""MiniAppService: orchestrates online-table reads and live-state mutations.

This is the Mini App's Service Layer. It composes the **existing** game services
(via :class:`ServiceProvider`) with the Redis-backed :class:`LiveStateStore`,
and enforces the online-play rules the REST/WS routes rely on:

* **Membership** — only players who belong to a game may see or act on its table.
* **Turn-gated mic** — only the current speaker may unmute or declare a challenge.
* **One challenge per turn** — enforced against live state.
* **Vote secrecy** — individual votes are never returned before the tally closes.

Every mutation returns the new :class:`LiveState`; the route layer is responsible
for persisting it (``store.save``) and publishing the resulting table snapshot to
the room. Keeping persistence/publish out of here keeps the service pure and
unit-testable, and lets the caller decide the transaction boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.miniapp.errors import (
    ChallengeAlreadyUsedError,
    NotSpeakerTurnError,
    NotTableMemberError,
    NotVotingPhaseError,
)
from app.miniapp.live_state import LiveState, LiveStateStore, Phase
from app.models.enums import PlayerStatus
from app.services import ServiceProvider
from app.utils.exceptions import (
    GameNotFoundError,
    NotGameCreatorError,
    PlayerNotInGameError,
)


@dataclass(frozen=True, slots=True)
class SeatView:
    """One seat as shown around the table (no role leak for other players)."""

    number: int | None
    user_id: int
    display_name: str
    is_creator: bool
    is_self: bool
    status: str
    # Only ever populated for the requesting player's own seat.
    own_role_code: str | None
    own_role_name_fa: str | None


@dataclass(frozen=True, slots=True)
class TableSnapshot:
    """The full client-facing table state for one viewer."""

    game_id: int
    code: str
    scenario_code: str
    status: str
    player_count: int
    is_creator: bool
    seats: list[SeatView]
    live: dict
    # Votes are only included (aggregated) once voting has closed.
    vote_tally: dict[str, int] | None


class MiniAppService:
    """Read/act facade for an online table, bound to one request's session."""

    def __init__(self, services: ServiceProvider, store: LiveStateStore) -> None:
        self._services = services
        self._store = store

    # --- Membership --------------------------------------------------------

    async def _load_game_or_404(self, game_id: int):
        game = await self._services.repos.games.get(game_id)
        if game is None:
            raise GameNotFoundError()
        return game

    async def game_by_code(self, code: str):
        """Resolve a 6-digit game code to its game row (or ``None``)."""
        return await self._services.repos.games.get_by_code(code)

    async def _members(self, game_id: int):
        """Active players of a game (eager-loaded user + assignment)."""
        return await self._services.repos.players.list_roster(game_id)

    async def ensure_member(self, *, game_id: int, user_id: int):
        """Return the requesting player's row, or raise if they're not in it."""
        for player in await self._members(game_id):
            if player.user_id == user_id:
                return player
        raise NotTableMemberError()

    # --- Snapshot ----------------------------------------------------------

    async def get_snapshot(self, *, game_id: int, user_id: int) -> TableSnapshot:
        """Build the table snapshot for a specific viewer (membership-checked)."""
        game = await self._load_game_or_404(game_id)
        await self.ensure_member(game_id=game_id, user_id=user_id)
        is_creator = game.creator_id == user_id

        players = await self._members(game_id)
        seats: list[SeatView] = []
        for p in players:
            is_self = p.user_id == user_id
            own_code = own_name = None
            if is_self and p.assignment is not None:
                gr = p.assignment.game_role
                own_code, own_name = gr.role_code, gr.display_name
            seats.append(
                SeatView(
                    number=p.number,
                    user_id=p.user_id,
                    display_name=(p.user.display_name if p.user else str(p.user_id)),
                    is_creator=(p.user_id == game.creator_id),
                    is_self=is_self,
                    status=p.status.value,
                    own_role_code=own_code,
                    own_role_name_fa=own_name,
                )
            )
        seats.sort(key=lambda s: (s.number is None, s.number or 0))

        live = await self._store.get(game_id)
        tally = None
        if live.phase == Phase.RESULTS.value and live.votes:
            tally = self._tally(live)

        return TableSnapshot(
            game_id=game.id,
            code=game.code,
            scenario_code=game.scenario_code,
            status=game.status.value,
            player_count=game.player_count,
            is_creator=is_creator,
            seats=seats,
            live=self._public_live(live),
            vote_tally=tally,
        )

    @staticmethod
    def _public_live(live: LiveState) -> dict:
        """Strip secret fields (raw votes) before sending to a client."""
        return {
            "phase": live.phase,
            "turn_number": live.turn_number,
            "timer_seconds": live.timer_seconds,
            "timer_running": live.timer_running,
            "challenge": live.challenge,
            "muted_all": live.muted_all,
            "speaking_number": live.speaking_number,
            "version": live.version,
            "has_votes": bool(live.votes),
        }

    @staticmethod
    def _tally(live: LiveState) -> dict[str, int]:
        counts: dict[str, int] = {}
        for target in live.votes.values():
            key = str(target)
            counts[key] = counts.get(key, 0) + 1
        return counts

    # --- Manager (creator-only) controls ----------------------------------

    async def _ensure_creator(self, *, game_id: int, user_id: int):
        game = await self._load_game_or_404(game_id)
        if game.creator_id != user_id:
            raise NotGameCreatorError()
        return game

    async def set_phase(
        self, *, game_id: int, user_id: int, phase: Phase, speaking_seconds: int
    ) -> LiveState:
        """Creator moves the table to a new phase and (re)arms the timer."""
        await self._ensure_creator(game_id=game_id, user_id=user_id)
        live = await self._store.get(game_id)
        live.phase = phase.value
        live.challenge = None
        if phase == Phase.VOTING:
            live.votes = {}
            live.muted_all = True
            live.speaking_number = None
            live.timer_running = False
        elif phase in (Phase.DAY, Phase.DEFENSE):
            live.timer_seconds = speaking_seconds
        return live

    async def start_turn(
        self, *, game_id: int, user_id: int, number: int, seconds: int
    ) -> LiveState:
        """Creator (or the turn engine) gives the floor to a seat number."""
        await self._ensure_creator(game_id=game_id, user_id=user_id)
        live = await self._store.get(game_id)
        live.speaking_number = number
        live.turn_number = number
        live.timer_seconds = seconds
        live.timer_running = True
        live.muted_all = False
        live.challenge = None
        return live

    async def set_timer(
        self, *, game_id: int, user_id: int, running: bool
    ) -> LiveState:
        """Creator pauses/resumes the speaking timer."""
        await self._ensure_creator(game_id=game_id, user_id=user_id)
        live = await self._store.get(game_id)
        live.timer_running = running
        return live

    async def adjust_time(
        self, *, game_id: int, user_id: int, delta: int
    ) -> LiveState:
        """Creator adds/removes speaking seconds (clamped at zero)."""
        await self._ensure_creator(game_id=game_id, user_id=user_id)
        live = await self._store.get(game_id)
        live.timer_seconds = max(0, live.timer_seconds + delta)
        return live

    async def mute_all(self, *, game_id: int, user_id: int) -> LiveState:
        """Creator force-mutes everyone (e.g. between turns)."""
        await self._ensure_creator(game_id=game_id, user_id=user_id)
        live = await self._store.get(game_id)
        live.muted_all = True
        live.speaking_number = None
        live.timer_running = False
        return live

    async def eliminate(self, *, game_id: int, user_id: int, number: int) -> None:
        """Creator eliminates a seat (persistent: marks the player LEFT)."""
        await self._ensure_creator(game_id=game_id, user_id=user_id)
        players = await self._members(game_id)
        target = next((p for p in players if p.number == number), None)
        if target is None:
            raise PlayerNotInGameError()
        target.status = PlayerStatus.LEFT

    # --- Player actions / server tick --------------------------------------

    async def tick(self, *, game_id: int) -> tuple[LiveState, bool]:
        """Advance the running timer by one second.

        Returns the (possibly updated) state and whether the turn just expired
        (so the caller can auto-advance and re-publish). No auth: called by the
        server's own timer loop, not by clients.
        """
        live = await self._store.get(game_id)
        expired = False
        if live.timer_running and live.timer_seconds > 0:
            live.timer_seconds -= 1
            if live.timer_seconds == 0:
                live.timer_running = False
                live.muted_all = True
                live.speaking_number = None
                expired = True
        return live, expired

    async def declare_challenge(
        self, *, game_id: int, user_id: int, target_number: int, seconds: int
    ) -> LiveState:
        """Current speaker challenges another seat (once per turn)."""
        me = await self.ensure_member(game_id=game_id, user_id=user_id)
        live = await self._store.get(game_id)
        if live.speaking_number is None or me.number != live.speaking_number:
            raise NotSpeakerTurnError()
        if live.challenge is not None:
            raise ChallengeAlreadyUsedError()
        live.challenge = {
            "challenger_number": me.number,
            "target_number": target_number,
            "seconds": seconds,
        }
        return live

    async def cast_vote(
        self, *, game_id: int, user_id: int, target_number: int
    ) -> LiveState:
        """Record a secret vote during the voting phase (last write wins)."""
        me = await self.ensure_member(game_id=game_id, user_id=user_id)
        if me.number is None:
            raise PlayerNotInGameError()
        live = await self._store.get(game_id)
        if live.phase != Phase.VOTING.value:
            raise NotVotingPhaseError()
        live.votes[str(me.number)] = target_number
        return live

    # --- Persistence helper ------------------------------------------------

    async def save(self, game_id: int, live: LiveState) -> LiveState:
        return await self._store.save(game_id, live)
