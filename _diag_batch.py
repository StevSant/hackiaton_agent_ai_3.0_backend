import asyncio, time
from sqlalchemy import select, text
async def main():
    from app.use_cases.rescore_all import _build_similarity
    from app.infrastructure.db.engine import create_engine, create_session_factory
    from app.infrastructure.db.models.siniestro import Siniestro
    eng=create_engine(); fac=create_session_factory(eng)
    sim=_build_similarity(fac)
    async with fac() as s:
        sins=list((await s.execute(select(Siniestro).limit(30))).scalars().all())
    items=[(x.id_siniestro, x.descripcion or "x"*40) for x in sins]
    t=time.time()
    await sim.index_many(items)
    print(f"index_many({len(items)}) took {time.time()-t:.2f}s", flush=True)
    # verify rows landed + nearest works on the freshly indexed corpus
    async with fac() as s:
        cnt=(await s.execute(text("select count(*) from claim_narratives where claim_id = any(:ids)"),{"ids":[i for i,_ in items]})).scalar()
    near=await sim.nearest(items[0][0], top_k=3)
    print(f"rows present={cnt}/{len(items)}  nearest[0]={[ (n.claim_id, round(n.similarity,3)) for n in near]}", flush=True)
    await eng.dispose()
asyncio.run(main())
