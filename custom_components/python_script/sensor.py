import logging

from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    try:
        if "file" in config:
            finename = hass.config.path(config["file"])
            with open(finename, "rt", encoding="utf-8") as f:
                source = f.read()
        elif "source" in config:
            source = config["source"]
        else:
            return
        code = compile(source, "<string>", "exec")
        async_add_entities([PythonSensor(code, config)], True)

    except Exception as e:
        _LOGGER.error("Error init python script sensor", exc_info=e)


class PythonSensor(Entity):
    def __init__(self, code, config: dict):
        self.code = code
        self.config = config
        self.attributes = {}

        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        self._attr_icon = config.get(CONF_ICON)
        self._attr_name = config.get(CONF_NAME)
        self._attr_unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)
        self._attr_unique_id = config.get(CONF_UNIQUE_ID)

    @property
    def state(self):
        return self._attr_state

    @state.setter
    def state(self, value):
        self._attr_state = value

    @property
    def state_attributes(self):
        return self.attributes

    def update(self):
        try:
            exec(self.code)
        except Exception as e:
            _LOGGER.error(f"Error update {self.name}", exc_info=e)
