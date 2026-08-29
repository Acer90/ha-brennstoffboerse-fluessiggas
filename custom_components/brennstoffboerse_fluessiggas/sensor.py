from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_REGION, CONF_VOLUME_LITERS, DOMAIN
from .coordinator import BrennstoffboerseFluessiggasCoordinator


@dataclass(frozen=True, kw_only=True)
class BrennstoffDescription(SensorEntityDescription):
    kind: str


DESCRIPTIONS: tuple[BrennstoffDescription, ...] = (
    BrennstoffDescription(
        key="price",
        name="Flüssiggas Preis",
        kind="price",
        native_unit_of_measurement="EUR/100L",
    ),
    BrennstoffDescription(
        key="change",
        name="Flüssiggas Preisänderung",
        kind="change",
        native_unit_of_measurement="EUR/100L",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: BrennstoffboerseFluessiggasCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [BrennstoffboerseFluessiggasSensor(coordinator, entry, description) for description in DESCRIPTIONS]
    )


class BrennstoffboerseFluessiggasSensor(
    CoordinatorEntity[BrennstoffboerseFluessiggasCoordinator], SensorEntity
):
    def __init__(
        self,
        coordinator: BrennstoffboerseFluessiggasCoordinator,
        entry: ConfigEntry,
        description: BrennstoffDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry

        region = str(entry.options.get(CONF_REGION, entry.data.get(CONF_REGION, ""))).strip()
        volume = int(entry.options.get(CONF_VOLUME_LITERS, entry.data.get(CONF_VOLUME_LITERS, 3000)))
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_name = f"Flüssiggas {region} {volume}L {description.name}"

    @property
    def native_value(self):
        data = self.coordinator.data
        if data is None:
            return None
        if self.entity_description.kind == "price":
            return data.price_eur_per_100l
        return data.change_eur_per_100l

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data
        if data is None:
            return None
        return {
            "region": data.region,
            "volume_liters": data.volume_liters,
            "source": "brennstoffboerse.de",
            "url": "https://brennstoffboerse.de/fluessiggas/fluessiggas-tagespreise.html",
        }
