from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    ALLOWED_VOLUMES_LITERS,
    CONF_REGION,
    CONF_VOLUME_LITERS,
    DEFAULT_VOLUME_LITERS,
    DOMAIN,
)
from .coordinator import async_fetch_regions

_LOGGER = logging.getLogger(__name__)


async def _region_schema(hass: HomeAssistant) -> vol.Schema:
    try:
        regions = await async_fetch_regions(hass)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Failed to fetch regions for selector: %s", err)
        regions = []

    if regions:
        region_selector: Any = selector.SelectSelector(
            selector.SelectSelectorConfig(options=regions, mode=selector.SelectSelectorMode.DROPDOWN)
        )
    else:
        region_selector = selector.TextSelector()

    return vol.Schema(
        {
            vol.Required(CONF_REGION): region_selector,
            vol.Required(CONF_VOLUME_LITERS, default=DEFAULT_VOLUME_LITERS): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[str(v) for v in ALLOWED_VOLUMES_LITERS],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


async def _region_schema_with_defaults(
    hass: HomeAssistant, *, default_region: str, default_volume_liters: int
) -> vol.Schema:
    base = await _region_schema(hass)
    return vol.Schema(
        {
            vol.Required(CONF_REGION, default=default_region): base.schema[CONF_REGION],
            vol.Required(CONF_VOLUME_LITERS, default=str(default_volume_liters)): base.schema[
                CONF_VOLUME_LITERS
            ],
        }
    )


class BrennstoffboerseFluessiggasConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            region = str(user_input[CONF_REGION]).strip()
            volume_liters = int(user_input[CONF_VOLUME_LITERS])
            if not region:
                errors[CONF_REGION] = "required"
            elif volume_liters not in ALLOWED_VOLUMES_LITERS:
                errors[CONF_VOLUME_LITERS] = "invalid_volume"
            else:
                await self.async_set_unique_id(f"{region.casefold()}_{volume_liters}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Flüssiggas {region} ({volume_liters}L)",
                    data={CONF_REGION: region, CONF_VOLUME_LITERS: volume_liters},
                )

        schema = await _region_schema(self.hass)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return BrennstoffboerseFluessiggasOptionsFlow(config_entry)


class BrennstoffboerseFluessiggasOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        super().__init__(config_entry)

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            region = str(user_input[CONF_REGION]).strip()
            volume_liters = int(user_input[CONF_VOLUME_LITERS])
            if not region:
                errors[CONF_REGION] = "required"
            elif volume_liters not in ALLOWED_VOLUMES_LITERS:
                errors[CONF_VOLUME_LITERS] = "invalid_volume"
            else:
                return self.async_create_entry(
                    title="",
                    data={CONF_REGION: region, CONF_VOLUME_LITERS: volume_liters},
                )

        default_region = str(
            self.config_entry.options.get(
                CONF_REGION, self.config_entry.data.get(CONF_REGION, "")
            )
        )
        default_volume_liters = int(
            self.config_entry.options.get(
                CONF_VOLUME_LITERS,
                self.config_entry.data.get(CONF_VOLUME_LITERS, DEFAULT_VOLUME_LITERS),
            )
        )
        schema = await _region_schema_with_defaults(
            self.hass,
            default_region=default_region,
            default_volume_liters=default_volume_liters,
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
