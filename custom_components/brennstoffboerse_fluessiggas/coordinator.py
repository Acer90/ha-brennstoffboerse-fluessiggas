from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from bs4 import BeautifulSoup

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ALLOWED_VOLUMES_LITERS,
    CONF_REGION,
    CONF_VOLUME_LITERS,
    UPDATE_INTERVAL,
    URL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class FluessiggasPriceData:
    region: str
    volume_liters: int
    price_eur_per_100l: float | None
    change_eur_per_100l: float | None


_EURO_NUMBER_RE = re.compile(r"([±\+\-]?[0-9]+(?:[\.,][0-9]+)?)\s*€", re.IGNORECASE)
_VOLUME_IN_HEADER_RE = re.compile(r"([0-9][0-9\.\s]{0,10})\s*L\b", re.IGNORECASE)


def _to_float_de(number_str: str) -> float:
    normalized = number_str.strip().replace(".", "").replace(",", ".")
    try:
        return float(Decimal(normalized))
    except (InvalidOperation, ValueError) as err:
        raise ValueError(f"Invalid number '{number_str}'") from err


def _extract_volume_liters(header_text: str) -> int | None:
    match = _VOLUME_IN_HEADER_RE.search(" ".join(header_text.split()))
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(1))
    if not digits:
        return None
    return int(digits)


def _extract_price_and_change(cell_text: str) -> tuple[float | None, float | None]:
    text = " ".join(cell_text.split())
    numbers = _EURO_NUMBER_RE.findall(text)
    if not numbers:
        return None, None

    price = _to_float_de(numbers[0])
    change: float | None = None
    if len(numbers) >= 2:
        change_raw = numbers[1]
        change = 0.0 if "±" in change_raw else _to_float_de(change_raw)
    return price, change


def _parse_regions_and_values(html: str) -> dict[str, dict[int, tuple[float | None, float | None]]]:
    """Returns: region -> volume_liters -> (price, change)."""
    soup = BeautifulSoup(html, "html.parser")

    target_table = None
    target_columns: dict[int, int] = {}
    for table in soup.find_all("table"):
        header_row = table.select_one("thead tr") or table.find("tr")
        if header_row is None:
            continue

        header_cells = header_row.find_all(["th", "td"], recursive=False)
        if len(header_cells) < 2:
            continue

        first_header = " ".join(header_cells[0].get_text(" ", strip=True).split()).casefold()
        if "region" not in first_header:
            continue

        columns: dict[int, int] = {}
        for idx, header_cell in enumerate(header_cells[1:], start=1):
            volume = _extract_volume_liters(header_cell.get_text(" ", strip=True))
            if volume in ALLOWED_VOLUMES_LITERS:
                columns[idx] = volume

        if columns:
            target_table = table
            target_columns = columns
            break

    if target_table is None:
        raise ValueError("Could not find price table")

    mapping: dict[str, dict[int, tuple[float | None, float | None]]] = {}
    rows = target_table.select("tbody tr") or target_table.find_all("tr")
    for tr in rows:
        row_cells = tr.find_all(["th", "td"], recursive=False)
        if len(row_cells) < 2:
            continue
        region = " ".join(row_cells[0].get_text(" ", strip=True).split())
        if not region:
            continue

        mapping.setdefault(region, {})
        for col_idx, volume in target_columns.items():
            if col_idx >= len(row_cells):
                continue
            price, change = _extract_price_and_change(row_cells[col_idx].get_text(" ", strip=True))
            mapping[region][volume] = (price, change)

    if not mapping:
        raise ValueError("Price table parsed but empty")
    return mapping


async def async_fetch_regions(hass: HomeAssistant) -> list[str]:
    session = async_get_clientsession(hass)
    async with session.get(URL, headers={"User-Agent": "HomeAssistant"}) as resp:
        if resp.status != 200:
            raise UpdateFailed(f"HTTP {resp.status}")
        html = await resp.text()
    parsed = _parse_regions_and_values(html)
    return sorted(parsed.keys(), key=lambda s: s.casefold())


class BrennstoffboerseFluessiggasCoordinator(DataUpdateCoordinator[FluessiggasPriceData]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        super().__init__(
            hass,
            _LOGGER,
            name=f"{entry.title}",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> FluessiggasPriceData:
        region = str(self.entry.options.get(CONF_REGION, self.entry.data.get(CONF_REGION, ""))).strip()
        volume_liters = int(
            self.entry.options.get(
                CONF_VOLUME_LITERS, self.entry.data.get(CONF_VOLUME_LITERS, 3000)
            )
        )
        if not region:
            raise UpdateFailed("No region configured")
        if volume_liters not in ALLOWED_VOLUMES_LITERS:
            raise UpdateFailed(f"Unsupported volume: {volume_liters}")

        session = async_get_clientsession(self.hass)
        try:
            async with session.get(URL, headers={"User-Agent": "HomeAssistant"}) as resp:
                if resp.status != 200:
                    raise UpdateFailed(f"HTTP {resp.status}")
                html = await resp.text()
        except Exception as err:
            raise UpdateFailed(f"Failed to fetch prices: {err}") from err

        try:
            data = _parse_regions_and_values(html)
            # Try exact match first, then casefold match.
            if region in data:
                region_key = region
            else:
                region_key = next(
                    (k for k in data.keys() if k.casefold() == region.casefold()),
                    None,
                )
                if region_key is None:
                    raise KeyError(region)

            price, change = data.get(region_key, {}).get(volume_liters, (None, None))
        except Exception as err:
            raise UpdateFailed(f"Failed to parse prices: {err}") from err

        return FluessiggasPriceData(
            region=region_key,
            volume_liters=volume_liters,
            price_eur_per_100l=price,
            change_eur_per_100l=change,
        )
