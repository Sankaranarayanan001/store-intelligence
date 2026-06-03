import aiosqlite
import csv
import os
from datetime import datetime, timezone

DB_PATH = os.getenv("DB_PATH", "./store.db")

async def load_pos_transactions(csv_path: str):
    if not os.path.exists(csv_path):
        print(f"POS file not found at {csv_path} — skipping")
        return 0

    loaded  = 0
    skipped = 0

    async with aiosqlite.connect(DB_PATH) as db:
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    order_date     = row.get("order_date", "").strip()
                    order_time     = row.get("order_time", "").strip()
                    transaction_id = row.get("invoice_number", "").strip()
                    total_amount   = float(row.get("total_amount", 0) or 0)

                    if not order_date or not order_time or not transaction_id:
                        skipped += 1
                        continue

                    dt = datetime.strptime(
                        f"{order_date} {order_time}",
                        "%d-%m-%Y %H:%M:%S"
                    )
                    timestamp = dt.replace(tzinfo=timezone.utc).isoformat()

                    await db.execute("""
                        INSERT OR IGNORE INTO pos_transactions
                        (transaction_id, store_id, timestamp, basket_value)
                        VALUES (?, ?, ?, ?)
                    """, (transaction_id, "STORE_BLR_002", timestamp, total_amount))

                    loaded += 1

                except Exception as e:
                    skipped += 1
                    continue

        await db.commit()

    print(f"POS transactions loaded: {loaded}, skipped: {skipped}")
    return loaded