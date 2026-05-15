"""gspread wrapper for procurement-clipping Google Sheet.

Sheet schema (tab 'NOTICIAS'):
  data | titulo | link | categoria | score_ia | motivo | score_humano | status | origem
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from src.common.config import settings

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
TAB = "NOTICIAS"


def _client() -> gspread.Client:
    info = json.loads(settings.google_service_account_json)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def _sheet() -> gspread.Worksheet:
    return _client().open_by_key(settings.google_sheet_id).worksheet(TAB)


def append_noticias(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    ws = _sheet()
    headers = ws.row_values(1)
    if not headers:
        headers = ["data", "titulo", "link", "categoria", "score_ia", "motivo",
                   "score_humano", "status", "origem"]
        ws.append_row(headers)
    values = [[str(r.get(h, "")) for h in headers] for r in rows]
    ws.append_rows(values, value_input_option="USER_ENTERED")
    logger.info("Saved %d news rows", len(rows))


def get_noticias_semana(dias: int = 7) -> list[dict[str, Any]]:
    """Return rows from the last N days."""
    ws = _sheet()
    records = ws.get_all_records()
    cutoff = datetime.now(timezone.utc) - timedelta(days=dias)
    result = []
    for r in records:
        if str(r.get("titulo", "")) in ("", "sem_noticias"):
            continue
        if str(r.get("status", "")) == "ignorado":
            continue
        data_str = str(r.get("data", "")).strip()
        try:
            if len(data_str) == 10:
                parts = data_str.split("-")
                dt = datetime(int(parts[0]), int(parts[1]), int(parts[2]), tzinfo=timezone.utc)
            else:
                dt = datetime.fromisoformat(data_str.replace("Z", "+00:00"))
            if dt >= cutoff or str(r.get("origem", "")) == "manual":
                result.append(r)
        except (ValueError, AttributeError):
            pass
    return result
