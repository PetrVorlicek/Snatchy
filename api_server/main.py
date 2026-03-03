from datetime import datetime
from decimal import Decimal
from typing import AsyncGenerator
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.models.models import RealEstateRecord
from app.model.session import AsyncSessionLocal
from fastapi import HTTPException


class Query(BaseModel):
    title: str | None = None
    published_before: datetime | None = None
    published_after: datetime | None = None
    price_under: Decimal | None = None
    price_over: Decimal | None = None
    flooring_under: float | None = None
    flooring_over: float | None = None


class RealEstateResponse(BaseModel):
    title: str
    published_at: datetime | None = None
    price: Decimal | None = None
    flooring_m_squared: float | None = None


app = FastAPI()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


@app.post("/query", response_model=list[RealEstateResponse])
async def query_records(query: Query, session: AsyncSession = Depends(get_session)):

    if not any(query.model_dump(exclude_none=True).values()):
        raise HTTPException(
            status_code=422, detail="At least one query parameter must be provided."
        )

    stmt = select(RealEstateRecord)

    if query.title is not None:
        stmt = stmt.where(RealEstateRecord.title.ilike(f"%{query.title}%"))
    if query.published_before is not None:
        stmt = stmt.where(RealEstateRecord.published_at <= query.published_before)
    if query.published_after is not None:
        stmt = stmt.where(RealEstateRecord.published_at >= query.published_after)
    if query.price_under is not None:
        stmt = stmt.where(RealEstateRecord.price <= query.price_under)
    if query.price_over is not None:
        stmt = stmt.where(RealEstateRecord.price >= query.price_over)
    if query.flooring_under is not None:
        stmt = stmt.where(RealEstateRecord.flooring_m_squared <= query.flooring_under)
    if query.flooring_over is not None:
        stmt = stmt.where(RealEstateRecord.flooring_m_squared >= query.flooring_over)
    stmt = stmt.limit(
        10
    )  # We have very limited context on the agent, so limit it to 10 now

    result = await session.execute(stmt)
    records = result.scalars().all()

    return records
