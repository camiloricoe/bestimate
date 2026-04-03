"""Bulk import addresses from CSV into the database."""

import csv
import sys

import click

from src.db.models import Property
from src.db.session import SyncSessionLocal, init_db_sync


@click.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--batch-size", default=1000, help="Commit every N rows")
def main(file: str, batch_size: int):
    """Import addresses from a CSV file into the scraping queue.

    CSV must have columns: address, city, state, zip_code (or zip)
    """
    init_db_sync()

    imported = 0
    with open(file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        session = SyncSessionLocal()

        try:
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

                if imported % batch_size == 0:
                    session.commit()
                    click.echo(f"  Imported {imported}...")

            session.commit()
        finally:
            session.close()

    click.echo(f"Done. Imported {imported} addresses.")


if __name__ == "__main__":
    main()
