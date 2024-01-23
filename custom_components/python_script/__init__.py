"""Component to allow running Python scripts.
https://docs.python.org/3/library/functions.html#compile
"""
import hashlib
import logging

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ServiceCallType
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


def md5(data: str) -> str:
    """
    Calculate the MD5 hash of the input string.

    Args:
        data (str): The input string to calculate the MD5 hash for.

    Returns:
        str: The MD5 hash of the input string.
    """
    return hashlib.md5(data.encode()).hexdigest()


async def async_setup(hass: HomeAssistant, hass_config: dict):
    config: dict = hass_config[DOMAIN]
    if CONF_REQUIREMENTS in config:
        hass.async_create_task(
            async_process_requirements(hass, DOMAIN, config[CONF_REQUIREMENTS])
        )

    cache_code = {}

    def handler(call: ServiceCall) -> ServiceResponse:
        """
        Handler function for processing a service call.

        Args:
            call (ServiceCall): The service call object containing the data for the call.

        Returns:
            ServiceResponse: The response returned by the function.

        Raises:
            None

        Description:
            This function is responsible for handling a service call. It receives a ServiceCall object as the input parameter, which contains the data for the call. The function first checks if the 'file' or 'source' parameter is present in the call data. If neither of them is present, an error message is logged and the function returns without any response.

            If either 'file' or 'source' is present, the function proceeds to retrieve the code from the cache or load it from the file or inline source. If the 'cache' parameter is set to False or the code is not found in the cache, the function loads the code from the specified file or inline source and compiles it.

            If the 'cache' parameter is set to True and the code is loaded from a file, the compiled code is stored in the cache for future use. Similarly, if the code is loaded from an inline source, it is stored in the cache with the source ID as the key.

            If the 'return_response' attribute of the service call is True, the function calls the 'execute_script' function with the necessary parameters and returns the response returned by it. Otherwise, the function returns None.

            Note: This function assumes that the necessary variables, such as '_LOGGER', 'hass', and 'cache_code', are already defined.
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


def execute_script(hass: HomeAssistant, data: dict, logger, code):
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
        _LOGGER.error(f"Error executing script", exc_info=e)
        service_response: JsonObjectType = {
            "stderr": f"Error executing script: {e}",
            "stdout": "",
            "returncode": 13,
        }
        return service_response if e else {}
