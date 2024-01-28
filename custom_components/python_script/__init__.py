"""Some dummy docs for execute_script."""
import hashlib
import logging
import os
import ast

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
from homeassistant.helpers.service import async_set_service_schema
from homeassistant.const import CONF_DESCRIPTION, CONF_NAME, SERVICE_RELOAD

_LOGGER = logging.getLogger(__name__)

DOMAIN = "python_script"
CONF_REQUIREMENTS = "requirements"
FOLDER = "python_scripts"
CONF_FIELDS = "fields"

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
        file = call.data.get("file") if call.service == "exec" else f"{hass.config.path(FOLDER)}/{call.service.replace('_f_', '/')}.py"
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


    def reload_scripts_handler(call: ServiceCall) -> None:
        """Handle reload service calls."""
        discover_scripts(hass, handler)
    hass.services.async_register(DOMAIN, SERVICE_RELOAD, reload_scripts_handler)

    discover_scripts(hass, handler)

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
            and k not in ["data", "NAME", "DESCRIPTION", "FIELDS"]
            or v is None
        }
        return response
    except Exception as e:
        _LOGGER.error(f"Error executing script", exc_info=e)
        return {"error": str(e)}

def discover_scripts(hass, handler):
    """Discover python scripts in folder."""
    path = hass.config.path(FOLDER)

    if not os.path.isdir(path):
        _LOGGER.warning("Folder %s not found in configuration folder", FOLDER)
        return

    existing = hass.services.async_services().get(DOMAIN, {}).keys()
    for existing_service in existing:
        if existing_service == SERVICE_RELOAD:
            continue
        if existing_service == "exec":
            continue
        hass.services.async_remove(DOMAIN, existing_service)

    for root, dirs, files in os.walk(path):
        for file in files:
            if file.endswith('.py'):
                try:
                    name = os.path.splitext(os.path.abspath(os.path.join(root, file)))[0].replace(path, '')[1:].replace('/', '_f_')
                    hass.services.async_register(
                        DOMAIN,
                        name,
                        handler,
                        supports_response=SupportsResponse.OPTIONAL,
                    )

                    services_dict = {}
                    fields_dict = {}
                    with open(os.path.join(root, file), 'r') as df:
                        data_file = df.readlines()
                    data_file = ''.join(data_file)
                    tree = ast.parse(data_file)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Assign):
                            for target in node.targets:
                                if isinstance(target, ast.Name) and target.id == 'NAME':
                                    services_dict.update(name = ast.literal_eval(node.value))
                                if isinstance(target, ast.Name) and target.id == 'DESCRIPTION':
                                    services_dict.update(description = ast.literal_eval(node.value))
                                if isinstance(target, ast.Name) and target.id == 'FIELDS':
                                    fields_dict = ast.literal_eval(node.value)
                    services_dict.update(fields = fields_dict | {"cache": {"default": True, "selector": {"boolean": ""}}})

                    service_desc = {
                        CONF_NAME: services_dict.get("NAME", name),
                        CONF_DESCRIPTION: services_dict.get("DESCRIPTION", ""),
                        CONF_FIELDS: services_dict.get("FIELDS", {}),
                    }
                    async_set_service_schema(hass, DOMAIN, name, service_desc)

                except Exception as err:
                    _LOGGER.warning(f"Error load discover scripts file service: {file}. Error: {err}")
