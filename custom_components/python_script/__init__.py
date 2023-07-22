"""Component to allow running Python scripts.
https://docs.python.org/3/library/functions.html#compile
"""
import hashlib
import logging

import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.requirements import async_process_requirements
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.helpers import config_validation as cv, entity_platform, service
from homeassistant.util.json import JsonObjectType

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
PYTHON_SCRIPTS_PRO_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional("file"): str,
        vol.Optional("source"): str,
        vol.Optional("cache"): bool,
    }
)


def md5(data: str):
    """
    Calculate the MD5 hash of the input string.

    Args:
        data (str): The input string to calculate the MD5 hash for.

    Returns:
        str: The MD5 hash of the input string.
    """
    return hashlib.md5(data.encode()).hexdigest()


async def async_setup(hass: HomeAssistantType, hass_config: dict):
    """
    Asynchronously sets up the integration.

    Args:
        hass (HomeAssistantType): The Home Assistant instance.
        hass_config (dict): The configuration for the integration.

    Returns:
        bool: True if the setup was successful, False otherwise.
    """
    config: dict = hass_config[DOMAIN]
    if CONF_REQUIREMENTS in config:
        hass.async_create_task(
            async_process_requirements(hass, DOMAIN, config[CONF_REQUIREMENTS])
        )

    cache_code = {}

    def handler(call: ServiceCall) -> ServiceResponse:
        """
        Executes the handler function for a service call.

        Args:
            call (ServiceCall): The service call object containing the data and context of the call.

        Returns:
            ServiceResponse: The response object containing the result of the handler execution.
        """
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

        if call.return_response:
            return execute_script(hass, call.data, _LOGGER, code) or {}
        return None

    hass.services.async_register(
        DOMAIN,
        "exec",
        handler,
        PYTHON_SCRIPTS_PRO_SERVICE_SCHEMA,
        SupportsResponse.OPTIONAL,
    )

    return True


def execute_script(hass, data, logger, code) -> ServiceResponse:
    """
    Execute a Python script.

    Parameters:
        hass (object): The Home Assistant Core object.
        data (object): Additional data passed to the script.
        logger (object): The logger object used for logging.
        code (str): The Python code to be executed.

    Returns:
        str: The response returned by the script.

    Raises:
        Exception: If there is an error executing the script.
    """
    try:
        _LOGGER.debug("Run python script")
        loc_vars = {}
        exec(code, {}, loc_vars)

        if loc_vars.get("return_response") is not None:
            service_response: JsonObjectType = {
                "stdout": loc_vars["return_response"],
                "stderr": "",
                "returncode": 0,
            }
            return service_response
        else:
            return {}
    except Exception as e:
        _LOGGER.exception(f"Error executing script: {e}")
        service_response: JsonObjectType = {
            "stdout": "",
            "stderr": f"Error executing script: {e}",
            "returncode": 13,
        }
        return service_response if e else {}
