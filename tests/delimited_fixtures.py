"""Delimited reference rows with an independently excludable first record."""

import csv
import io


def reviewed_delimited_table(kind: str) -> tuple[str, bytes]:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter="\t" if kind == "tsv" else ",")
    writer.writerow(["Private header", "Private conditions"])
    writer.writerow(["XGPON", "التغطية مطلوبة. " * 80])
    writer.writerow(["Private appendix", "Never publish"])
    mime = "text/tab-separated-values" if kind == "tsv" else "text/csv"
    return mime, stream.getvalue().encode("utf-8-sig")
