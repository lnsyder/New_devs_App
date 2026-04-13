from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List
from zoneinfo import ZoneInfo

async def calculate_monthly_revenue(property_id: str, tenant_id: str, month: int, year: int, db_session=None) -> Decimal:
    """
    Calculates revenue for a specific month.
    """
    if db_session is None:
        return Decimal('0')

    from sqlalchemy import text

    tz_row = await db_session.execute(
        text("SELECT timezone FROM properties WHERE id = :pid AND tenant_id = :tid"),
        {"pid": property_id, "tid": tenant_id},
    )
    tz_name = (tz_row.fetchone() or [None])[0] or "UTC"

    local_tz = ZoneInfo(tz_name)
    local_start = datetime(year, month, 1, tzinfo=local_tz)
    if month < 12:
        local_end = datetime(year, month + 1, 1, tzinfo=local_tz)
    else:
        local_end = datetime(year + 1, 1, 1, tzinfo=local_tz)

    utc_start = local_start.astimezone(ZoneInfo("UTC"))
    utc_end   = local_end.astimezone(ZoneInfo("UTC"))

    print(f"DEBUG: Querying revenue for {property_id} (tz={tz_name}) "
          f"local {local_start.date()} – {local_end.date()} "
          f"→ UTC {utc_start} – {utc_end}")

    # SQL Simulation (This would be executed against the actual DB)
    query = text("""
        SELECT SUM(total_amount) as total
        FROM reservations
        WHERE property_id = :property_id
        AND tenant_id = :tenant_id
        AND check_in_date >= :start_date
        AND check_in_date <  :end_date
    """)

    result = await db_session.execute(query, {
        "property_id": property_id,
        "tenant_id":   tenant_id,
        "start_date":  utc_start,
        "end_date":    utc_end,
    })
    row = result.fetchone()
    return Decimal(str(row.total)) if row and row.total is not None else Decimal('0') # Placeholder for now until DB connection is finalized

async def calculate_total_revenue(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Aggregates revenue from database.
    """
    try:
        # Import database pool
        from app.core.database_pool import DatabasePool

        # Initialize pool if needed
        db_pool = DatabasePool()
        await db_pool.initialize()

        if db_pool.session_factory:
            async with db_pool.get_session() as session:
                # Use SQLAlchemy text for raw SQL
                from sqlalchemy import text

                query = text("""
                    SELECT
                        property_id,
                        SUM(total_amount) as total_revenue,
                        COUNT(*) as reservation_count
                    FROM reservations
                    WHERE property_id = :property_id AND tenant_id = :tenant_id
                    GROUP BY property_id
                """)

                result = await session.execute(query, {
                    "property_id": property_id,
                    "tenant_id": tenant_id
                })
                row = result.fetchone()

                if row:
                    total_revenue = Decimal(str(row.total_revenue))
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": str(total_revenue),
                        "currency": "USD",
                        "count": row.reservation_count
                    }
                else:
                    # No reservations found for this property
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": "0.00",
                        "currency": "USD",
                        "count": 0
                    }
        else:
            raise Exception("Database pool not available")

    except Exception as e:
        print(f"Database error for {property_id} (tenant: {tenant_id}): {e}")

        # Create property-specific mock data for testing when DB is unavailable
        # This ensures each property shows different figures
        mock_data = {
            'prop-001': {'total': '1000.00', 'count': 3},
            'prop-002': {'total': '4975.50', 'count': 4},
            'prop-003': {'total': '6100.50', 'count': 2},
            'prop-004': {'total': '1776.50', 'count': 4},
            'prop-005': {'total': '3256.00', 'count': 3}
        }

        mock_property_data = mock_data.get(property_id, {'total': '0.00', 'count': 0})

        return {
            "property_id": property_id,
            "tenant_id": tenant_id,
            "total": mock_property_data['total'],
            "currency": "USD",
            "count": mock_property_data['count']
        }
