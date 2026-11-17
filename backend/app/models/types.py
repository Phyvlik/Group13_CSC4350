import uuid
from decimal import Decimal
from typing import Annotated

from sqlalchemy import Numeric, Uuid, text
from sqlalchemy.orm import mapped_column

# UUID primary key generated in Python, with a Postgres default as a fallback for raw SQL inserts.
UuidPk = Annotated[
    uuid.UUID,
    mapped_column(Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")),
]

# Shared precision for prices, quantities, cash, and metric values.
Amount = Annotated[Decimal, mapped_column(Numeric(18, 6))]
