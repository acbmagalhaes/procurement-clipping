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

TAB_NOTICIAS = "NOTICIAS"
HEADERS = ["data", "titulo", "link", "categoria", "score_ia", "motivo", "score_humano", "status", "origem"]


def _client() -> gspread.Client:
    info = json.loads(settings.google_service_account_json)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def _sheet() -> gspread.Worksheet:
    return _client().open_by_key(settings.google_sheet_id).worksheet(TAB_NOTICIAS)


def append_news(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    ws = _sheet()
    headers = ws.row_values(1) or HEADERS
    values = [[str(r.get(h, "")) for h in headers] for r in rows]
    ws.append_rows(values, value_input_option="USER_ENTERED")


def get_news_last_n_days(days: int = 7) -> list[dict[str, Any]]:
    ws = _sheet()
    records = ws.get_all_records()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = []
    for r in records:
        if str(r.get("titulo", "")) == "sem_noticias":
            continue
        if str(r.get("status", "")).lower() == "ignorado":
            continue
        data_str = str(r.get("data", "")).strip()
        try:
            d = datetime.fromisoformat(data_str) if "T" in data_str else datetime.strptime(data_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if d >= cutoff or str(r.get("origem", "")) == "manual":
                result.append(dict(r))
        except ValueError:
            result.append(dict(r))
    return result
