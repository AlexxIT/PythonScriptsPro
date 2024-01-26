"""Some dummy docs for execute_script."""
import hashlib
import logging

import voluptuous as vol
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.requirements import async_process_requirements

_LOGGER = logging.getLogger(__name__)

DOMAIN = "python_script"
CONF_REQUIREMENTS = "requirements"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_REQUIREMENTS): cv.ensure_list,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional("file"): str,
        vol.Optional("source"): str,
        vol.Optional("cache"): bool,
    },
    extra=vol.ALLOW_EXTRA,
)


def md5(data: str) -> str:
    return hashlib.md5(data.encode()).hexdigest()


async def async_setup(hass: HomeAssistant, hass_config: ConfigType):
    config: dict = hass_config[DOMAIN]
    if CONF_REQUIREMENTS in config:
        hass.async_create_task(
            async_process_requirements(hass, DOMAIN, config[CONF_REQUIREMENTS])
        )

    cache_code = {}

    def handler(call: ServiceCall) -> ServiceResponse:
        # Run with SyncWorker
        file = call.data.get("file")
        srcid = md5(call.data["source"]) if "source" in call.data else None
        cache = call.data.get("cache", True)

        if not (file or srcid):
            _LOGGER.error("Either file or source is required in params")
            return

        code = cache_code.get(file or srcid)

        if not cache or not code:
            if file:
                _LOGGER.debug("Load code from file")

                file = hass.config.path(file)
                with open(file, encoding="utf-8") as f:
                    code = compile(f.read(), file, "exec")

                if cache:
                    cache_code[file] = code

            else:
                _LOGGER.debug("Load inline code")

                code = compile(call.data["source"], "<string>", "exec")

                if cache:
                    cache_code[srcid] = code

        else:
            _LOGGER.debug("Load code from cache")

        return execute_script(hass, call.data, _LOGGER, code)

    hass.services.async_register(
        DOMAIN,
        "exec",
        handler,
        SERVICE_SCHEMA,
        SupportsResponse.OPTIONAL,
    )

    return True


def execute_script(hass: HomeAssistant, data: dict, logger, code) -> ServiceResponse:
    try:
        _LOGGER.debug("Run python script")
        vars = {**globals(), **locals()}
        exec(code, vars)
        response = {
            k: v
            for k, v in vars.items()
            if isinstance(v, (dict, list, str, int, float, bool))
            and k not in globals()
            and k != "data"
            or v is None
        }
        return response
    except Exception as e:
        _LOGGER.error(f"Error executing script", exc_info=e)
        return {"error": str(e)}
