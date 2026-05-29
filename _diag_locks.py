import asyncio
from sqlalchemy import text
async def main():
    from app.infrastructure.db.engine import create_engine, create_session_factory
    eng=create_engine(); fac=create_session_factory(eng)
    async with fac() as s:
        rows=(await s.execute(text(
          "select pid, state, wait_event_type, wait_event, "
          "round(extract(epoch from (now()-xact_start))) as xact_age_s, "
          "left(query,80) as q "
          "from pg_stat_activity "
          "where datname = current_database() and pid <> pg_backend_pid() "
          "and state is not null order by xact_start nulls last"
        ))).fetchall()
        for r in rows:
            print(dict(r._mapping), flush=True)
    await eng.dispose()
asyncio.run(main())
