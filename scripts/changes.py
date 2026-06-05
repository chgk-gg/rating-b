from typing import Dict, List

import mmh3

_MASK64 = (1 << 64) - 1


def _row_hash(table: str, row: dict) -> int:
    payload = table + "\x1f" + "\x1f".join(str(row[column]) for column in row)
    return mmh3.hash64(payload, signed=False)[0]


# Fingerprints the exact rows that would be written for a release, so every written
# column is covered and we can skip the write when nothing changed. The per-row
# hashes are summed (commutative), making the result independent of row order; the
# table name is folded into each row hash so identical rows in different tables do
# not collide. The result is mapped into signed 64-bit range for Postgres bigint.
def fingerprint(table_rows: Dict[str, List[dict]]) -> int:
    total = 0
    for table, rows in table_rows.items():
        for row in rows:
            total = (total + _row_hash(table, row)) & _MASK64
    return total - (1 << 64) if total >= (1 << 63) else total
