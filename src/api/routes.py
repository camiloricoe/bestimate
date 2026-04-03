"""API routes for import, export, status, and metrics."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone

from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import func, select

from src.db.models import Property, Result
from src.db.session import AsyncSessionLocal

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/status")
async def status():
    """Get current scraping progress."""
    async with AsyncSessionLocal() as session:
        counts = {}
        for s in ["pending", "queued", "in_progress", "completed", "failed", "blocked"]:
            count = await session.scalar(
                select(func.count(Property.id)).where(Property.status == s)
            )
            counts[s] = count or 0

        total = await session.scalar(select(func.count(Property.id)))
        results_count = await session.scalar(select(func.count(Result.id)))
        avg_zestimate = await session.scalar(select(func.avg(Result.zestimate)))

    return {
        "total_properties": total or 0,
        "by_status": counts,
        "total_results": results_count or 0,
        "avg_zestimate": round(avg_zestimate, 2) if avg_zestimate else None,
        "completion_rate": round(counts["completed"] / total * 100, 1) if total else 0,
    }


@router.post("/import")
async def import_addresses(file: UploadFile = File(...)):
    """Import addresses from a CSV file.

    Expected CSV columns: address, city, state, zip_code
    """
    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    imported = 0
    async with AsyncSessionLocal() as session:
        for row in reader:
            address = row.get("address", "").strip()
            if not address:
                continue

            prop = Property(
                address=address,
                city=row.get("city", "").strip(),
                state=row.get("state", "").strip(),
                zip_code=str(row.get("zip_code", row.get("zip", ""))).strip()[:5],
                status="pending",
            )
            session.add(prop)
            imported += 1

        await session.commit()

    return {"imported": imported, "message": f"Imported {imported} addresses"}


@router.get("/export")
async def export_results(format: str = Query("csv", enum=["csv", "json"])):
    """Export all completed results."""
    async with AsyncSessionLocal() as session:
        stmt = select(Result).order_by(Result.scraped_at)
        results = (await session.scalars(stmt)).all()

    if format == "json":
        data = [
            {
                "zpid": r.zpid,
                "zestimate": r.zestimate,
                "price": r.price,
                "address": r.address,
                "city": r.city,
                "state": r.state,
                "zip_code": r.zip_code,
                "beds": r.beds,
                "baths": r.baths,
                "sqft": r.sqft,
                "lot_size_sqft": r.lot_size_sqft,
                "year_built": r.year_built,
                "property_type": r.property_type,
                "scraped_at": r.scraped_at.isoformat() if r.scraped_at else None,
            }
            for r in results
        ]
        return Response(
            content=json.dumps(data, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=results.json"},
        )

    # CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "zpid", "zestimate", "price", "address", "city", "state", "zip_code",
        "beds", "baths", "sqft", "lot_size_sqft", "year_built", "property_type", "scraped_at",
    ])
    for r in results:
        writer.writerow([
            r.zpid, r.zestimate, r.price, r.address, r.city, r.state, r.zip_code,
            r.beds, r.baths, r.sqft, r.lot_size_sqft, r.year_built, r.property_type,
            r.scraped_at.isoformat() if r.scraped_at else "",
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=results.csv"},
    )


@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
