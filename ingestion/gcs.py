"""Zapis surowych odpowiedzi do warstwy raw na GCS.

Ścieżka deterministyczna per interwał (idempotentność):
    raw/source=<źródło>/season=<rrrr>/ingest_date=<rrrr-mm-dd>/<plik>.json

Implementacja klienta GCS dojdzie w fazie 2.
"""
