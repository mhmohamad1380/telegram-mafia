# 🎭 Mafia Game Management Bot

A production-ready Telegram bot for **managing** Iranian-style Mafia games:
create a game, let players join, randomly and atomically assign unique roles and
seat numbers, reveal each role privately, and control the game lifecycle.

The bot deliberately does **not** run the game itself (no night/day phases,
voting, or in-game role powers). It only handles setup and role distribution.

Built with **Python 3.13**, **aiogram 3**, **SQLAlchemy 2 (async)**,
**PostgreSQL**, **Alembic**, **Redis** (FSM storage), **structlog**, and
**Pydantic Settings**, following Clean Architecture with a Repository pattern,
Service layer, and Dependency Injection.

---

## ✨ Features

- `/create_game` wizard: choose player count → select roles via inline keyboard
  (✅/❌ toggles) → get a unique **6-digit game code**.
- `/join`: enter the code, pick a **unique seat number**, receive a **random,
  unique role** revealed privately.
- Creator is a normal player too (joins, picks a number, gets a role).
- Creator controls: **status**, **start game**, **full roster** (private),
  **finish game**.
- **Race-free** number and role assignment using `SELECT ... FOR UPDATE` row
  locks plus guarded atomic `UPDATE`s, all inside a single transaction.
- Leaving a lobby frees the seat and returns the role to the pool.
- `/roles`: list every supported role, grouped by team.
- Structured logging, typed settings, full type hints, and an append-only audit
  log of game events.

---

## 🎲 Supported Roles

**Citizens:** شهروند ساده، دکتر، کارآگاه، تک‌تیرانداز، روانشناس، رویین‌تن،
زره‌پوش، کشیش، قاضی، شهردار، محافظ، خبرنگار

**Mafia:** رئیس مافیا (گادفادر)، مافیای ساده، ناتاشا، مذاکره‌کننده، بمب‌گذار،
وکیل، گروگان‌گیر

**Independent:** جوکر، قاتل سریالی، نوستراداموس، فراماسون

Roles live in a single catalog (`app/utils/role_catalog.py`) and are seeded into
the database on startup. Add a new role by extending the `RoleCode` enum and the
catalog — everything else adapts automatically.

---

## 🏗 Architecture

```
app/
├── bot/                    # Presentation layer (aiogram)
│   ├── handlers/           # Command & callback handlers (routers)
│   ├── middlewares/        # DB session/DI + auth middlewares
│   ├── filters/            # Custom filters (e.g. private chat)
│   ├── keyboards/          # Inline keyboard builders
│   ├── callbacks.py        # Typed CallbackData factories
│   ├── states.py           # FSM state groups
│   └── texts.py            # Persian user-facing strings/formatters
├── services/               # Business logic (Service layer)
│   ├── game_service.py         # create/configure/start/finish
│   ├── lobby_service.py        # join/number/leave (row-locked)
│   ├── assignment_service.py   # atomic random role assignment
│   ├── player_service.py       # player queries + private role reveal
│   ├── roster_service.py       # creator-only full roster
│   ├── role_service.py         # role catalog access
│   └── randomizer_service.py   # secure randomness
├── repositories/           # Data access (Repository pattern)
├── models/                 # SQLAlchemy ORM models + enums
├── schemas/                # Pydantic DTOs
├── database/               # Base, async session, seed, Alembic migrations
├── config/                 # Settings + logging
├── utils/                  # Role catalog, exceptions, code helpers
└── main.py                 # Entry point (wiring + polling)
```

**Layering rules**

- Handlers never touch the database directly — they call services.
- Services never issue SQL directly — they use repositories.
- Repositories never commit — the DB middleware owns the transaction per update.
- ORM objects never leave the service layer — services return Pydantic DTOs.

### Database schema

`users`, `roles`, `games`, `game_roles`, `game_players`, `role_assignments`,
`game_events` — with primary/foreign keys, indexes, unique constraints, check
constraints, native PostgreSQL enums, and cascade rules. See
`app/database/migrations/versions/0001_initial_schema.py`.

### Concurrency & correctness

- The game row is locked with `SELECT ... FOR UPDATE` before any lobby mutation,
  serializing concurrent joins / number picks / assignments per game.
- Seat numbers are protected by a `UNIQUE (game_id, number)` constraint.
- Role slots are claimed with a guarded `UPDATE game_roles SET remaining =
  remaining - 1 WHERE id = :id AND remaining > 0`, so the same role can never be
  assigned twice even under contention.
- Each player has at most one role (`UNIQUE (player_id)` on `role_assignments`).

---

## 🚀 Running with Docker (recommended)

1. Copy the environment template and set your bot token:

   ```bash
   cp .env.example .env
   # edit .env and set BOT_TOKEN=... (from @BotFather)
   ```

2. Build and start everything (Postgres, Redis, and the bot):

   ```bash
   docker compose up --build
   ```

   On startup the bot container runs `alembic upgrade head` (creating all
   tables) and then launches the bot, which seeds the role catalog.

3. Open Telegram, message your bot, and send `/start`.

To stop: `docker compose down` (add `-v` to also remove data volumes).

---

## 🧑‍💻 Running locally (without Docker)

Requirements: Python 3.13, a running PostgreSQL, and a running Redis.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set BOT_TOKEN and point POSTGRES_*/REDIS_* at your local services

# Apply migrations
alembic upgrade head

# Start the bot
python -m app.main
```

---

## 🗂 Environment variables

See `.env.example` for the full list. Key ones:

| Variable            | Description                              | Default     |
| ------------------- | ---------------------------------------- | ----------- |
| `BOT_TOKEN`         | Telegram bot token from @BotFather       | —           |
| `POSTGRES_HOST`     | PostgreSQL host                          | `localhost` |
| `POSTGRES_PORT`     | PostgreSQL port                          | `5432`      |
| `POSTGRES_USER`     | PostgreSQL user                          | `mafia`     |
| `POSTGRES_PASSWORD` | PostgreSQL password                      | `mafia`     |
| `POSTGRES_DB`       | PostgreSQL database                      | `mafia`     |
| `REDIS_HOST`        | Redis host                               | `localhost` |
| `REDIS_PORT`        | Redis port                               | `6379`      |
| `REDIS_DB`          | Redis database index                     | `0`         |
| `LOG_LEVEL`         | `DEBUG`/`INFO`/`WARNING`/`ERROR`         | `INFO`      |
| `LOG_CONSOLE`       | Pretty console logs (`true`) or JSON     | `true`      |
| `ENVIRONMENT`       | `development` / `production`             | `development` |

> In Docker Compose, `POSTGRES_HOST` and `REDIS_HOST` are overridden to the
> service names (`postgres`, `redis`) automatically.

---

## 🕹 Usage flow

**Creator**

1. `/create_game`
2. Pick or type the number of players.
3. Toggle roles until the selected count equals the player count, then confirm.
4. Share the 6-digit code. Join your own game with `/join` like everyone else.
5. Use **status** to watch progress; **start** once everyone has a role;
   **roster** to privately see all roles; **finish** to end.

**Players**

1. `/join` → enter the code.
2. Pick a free seat number.
3. Tap **دریافت نقش** to get your role, revealed privately.

---

## 🧩 Migrations

```bash
# Create a new autogenerated migration after model changes
alembic revision --autogenerate -m "describe change"

# Apply
alembic upgrade head

# Roll back one step
alembic downgrade -1
```

---

## ✅ End-to-End tests

A comprehensive, self-contained **E2E QA suite** lives in `tests/`. It drives the
**real service layer** against a live PostgreSQL + Redis (the same ones the bot
uses) and validates all 25 functional areas — startup, the create-game wizard,
scenarios, lobby/turn flow, role assignment, custom roles, keyboards, callback
round-trips, FSM states, and **race conditions** (concurrent joins, number picks,
and deletes).

The runner never halts on the first failure: every check is recorded and a
single, section-grouped report is printed at the end with the exact location,
cause, exception, suggested fix, and traceback for each problem. The process exit
code is `0` only when every check passes, so it doubles as a CI/release gate.

Run it inside the app container (recommended, so all deps + env are present):

```bash
# Bring up the datastores, then run the suite
docker compose up -d postgres redis
docker compose run --rm -v "$(pwd)/tests:/app/tests" bot python -m tests.e2e
```

Or locally, with the DB/Redis reachable via your environment:

```bash
alembic upgrade head        # ensure the schema + seed data exist
python -m tests.e2e
```

Expected tail of a healthy run:

```
Total Tests : 312
Passed      : 312
Failed      : 0
Warnings    : 0

✅ Project is production ready.
```

Suite layout:

| File | Responsibility |
| --- | --- |
| `tests/reporter.py` | Error-collecting reporter + final report renderer |
| `tests/harness.py` | App context: engine/session, Redis, fake users, cleanup |
| `tests/flows.py` | Reusable high-level game flows (create/join/turns/start) |
| `tests/sections.py` | The 25 functional test sections |
| `tests/e2e.py` | Runnable entry point (`python -m tests.e2e`) |

---

## 📄 License

Provided as-is for educational and personal use.
