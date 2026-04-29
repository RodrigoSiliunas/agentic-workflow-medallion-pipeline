"""Conftest para integration tests — usa Postgres real via Docker.

Requer que o container `flowertex-postgres` esteja rodando com o DB
`flowertex_test` criado. Cada teste trunca todas as tabelas pra isolar.
Se o DB nao estiver acessivel, toda a suite e pulada.
"""

import os
import uuid
from collections.abc import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.database.session import get_db
from app.main import app
from app.models.base import Base

# Tests run com self-serve aberto — gating eh prod-only.
settings.REGISTRATION_OPEN = True

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    settings.DATABASE_URL.replace("/flowertex", "/flowertex_test"),
)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_engine():
    """Cria engine session-scoped + schema inicial."""
    try:
        engine = create_async_engine(TEST_DB_URL, pool_pre_ping=True)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        pytest.skip(f"Postgres de teste indisponivel: {e}", allow_module_level=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def _clear_rate_limiter():
    """Limpa o rate limiter in-memory entre testes pra evitar rate limiting."""
    from app.middleware.rate_limiter import _memory_store

    _memory_store.clear()
    yield
    _memory_store.clear()


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def _truncate_all_tables(test_engine):
    """Trunca todas as tabelas entre testes pra garantir isolamento."""
    yield
    async with test_engine.begin() as conn:
        table_names = ", ".join(
            f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables)
        )
        await conn.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Session imperative pra fixtures/seed dentro dos testes."""
    session_maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session


@pytest_asyncio.fixture(loop_scope="session")
async def http_client(test_engine) -> AsyncGenerator[httpx.AsyncClient, None]:
    """HTTP client que fala com o ASGI app via DB override."""
    session_maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(loop_scope="session")
async def registered_company(http_client: httpx.AsyncClient) -> dict:
    """Cria uma company + admin via /register-company. Retorna tokens + credenciais."""
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "company_name": f"Test Co {suffix}",
        "company_slug": f"test-{suffix}",
        "admin_name": "Test Admin",
        "admin_email": f"admin-{suffix}@example.com",
        "admin_password": "test1234",
    }
    response = await http_client.post("/api/v1/auth/register-company", json=payload)
    assert response.status_code == 201, response.text
    data = response.json()
    data["email"] = payload["admin_email"]
    data["password"] = payload["admin_password"]
    return data


@pytest_asyncio.fixture(loop_scope="session")
async def auth_headers(registered_company: dict) -> dict:
    return {"Authorization": f"Bearer {registered_company['access_token']}"}
