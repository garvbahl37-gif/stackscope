"""Report builders: Excel analyst pack, research note, BI export."""

from __future__ import annotations


def build_all() -> list[str]:
    from ..warehouse.build import connect
    from . import bi_export, data_dictionary, excel, research_note

    con = connect(read_only=True)
    try:
        return [
            f"Excel analyst pack -> {excel.build(con)}",
            f"Research note -> {research_note.build(con)}",
            f"Power BI / Tableau pack -> {bi_export.build(con)}",
            f"Data dictionary -> {data_dictionary.build(con)}",
        ]
    finally:
        con.close()
