# Python Scripts for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![Donate](https://img.shields.io/badge/donate-Coffee-yellow.svg)](https://www.buymeacoffee.com/AlexxIT)
[![Donate](https://img.shields.io/badge/donate-Yandex-red.svg)](https://money.yandex.ru/to/41001428278477)

Custom component for easy run Python Scripts from Home Assistant. Better version of default [python_script](https://www.home-assistant.io/integrations/python_script/) component.

## Installation

**Method 1.** [HACS](https://hacs.xyz/) custom repo:

> HACS > Integrations > 3 dots (upper top corner) > Custom repositories > URL: `AlexxIT/PythonScriptsPro`, Category: Integration > Add > wait > PythonScriptsPro > Install

**Method 2.** Manually copy `python_script` folder from [latest release](https://github.com/AlexxIT/PythonScriptsPro/releases/latest) to `/config/custom_components` folder.

## Configuration

**Important:** The component replaces the standard [python_script](https://www.home-assistant.io/integrations/python_script/) component!

Add to `configuration.yaml`:

```yaml
python_script:  # no S at the end!
```

If you need to use additional python libraries, the component can install them:

```yaml
python_script:
  requirements:
  - paramiko>=2.7.1
```

## Use python_script.exec service

- The component creates the `python_script.exec` service.
- You can run an external python script located in any folder (use `file` param).
- Or you can paste python source code directly into your YAML (use `source` param).
- You can **import** and use any library in your python scripts. The standard `python_script` component does not allow this.
- You can pass any variables to your script, just like in the standard `python_script`.
- The component compile and caches the executable code for faster next launch. If you want change python file without reload HA, you can disable cache with the `cache: false` param.

The following variables are available in the script:
- `hass` - The [Home Assistant API](https://www.home-assistant.io/developers/development_hass_object/)
- `data` - The data passed to the Python Script service call
- `logger` - A logger to allow you to log messages

### Run script from python file

Show Home Assistant start time in Notification. Using my another component [StartTime](https://github.com/AlexxIT/StartTime). Pass variable to script.

```yaml
script:
  test_file:
    sequence:
    - service: python_script.exec
      data_template:  # use `data_template` if you have Jinja2 templates in params
        file: path_to/test_file.py  # relative path from config folder
        cache: false  # disable cache if you want change python file without reload HA
        title: Python from file test
        time_val: "{{ states('sensor.start_time')|round }}"
```

**test_file.py**

```python
logger.debug(data)
hass.services.call('persistent_notification', 'create', {
  'title': data['title'],
  'message': f"Home Assistant starts in { data['time_val'] } seconds"
})

```

### Run script from inline source

Show your IP address in Notification. Using `requests` library. It is installed by default with Home Assistant.

```yaml
script:
  test_source:
    sequence:
    - service: python_script.exec
      data:
        title: Python inline test
        source: |
          import requests
          r = requests.get('https://api.ipify.org?format=json')
          resp = r.json()
          logger.debug(resp)
          hass.services.call('persistent_notification', 'create', {
            'title': data['title'],
            'message': f"My IP: { resp['ip'] }"
          })
```

### Example remote SSH-command run

This example completely repeats the logic of my other component - [SSHCommand](https://github.com/AlexxIT/SSHCommand).

There is no `paramiko` library by default, but the component can install it. This will work with Hass.io or Docker.

```yaml
python_script:
  requirements:
  - paramiko>=2.7.1

script:
  ssh_command:
    sequence:
    - service: python_script.exec
      data:
        file: path_to/ssh_command.py
        host: 192.168.1.123  # optional
        user: myusername  # optional
        pass: mypassword  # optional
        command: ls -la
```

**ssh_command.py**

```python
from paramiko import SSHClient, AutoAddPolicy

host = data.get('host', '172.17.0.1')
port = data.get('port', 22)
username = data.get('user', 'pi')
password = data.get('pass', 'raspberry')
command = data.get('command')

client = SSHClient()
client.set_missing_host_key_policy(AutoAddPolicy())
client.connect(host, port, username, password)
stdin, stdout, stderr = client.exec_command(command)
resp = stdout.read()
stderr.read()
client.close()

logger.info(f"SSH response:\n{ resp.decode() }")
```

### Example using hass API

Example read states and attributes, call services and fire events in python scripts.

```python
state1 = hass.states.get('sensor.start_time').state
name1 = hass.states.get('sensor.start_time').attributes['friendly_name']

if float(state1) < 30:
    hass.services.call('persistent_notification', 'create', {
        'title': "My Python Script",
        'message': "Home Assistant started very quickly"
    })

    hass.states.set('sensor.start_time', state1, {
        'friendly_name': f"Fast {name1}"
    })

else:
    hass.services.call('persistent_notification', 'create', {
        'title': "My Python Script",
        'message': "Home Assistant was running for a very long time"
    })

    hass.states.set('sensor.start_time', state1, {
        'friendly_name': f"Slow {name1}"
    })

hass.bus.fire('my_event_name', {
    'param1': 'value1'
})
```

## Use python_script sensors

The component allows you to create sensors.

Config:
- You can use inline `source` or load python code from `file` (relative path from config folder).
- You can set `name`, `icon`, `unit_of_measurement` and `scan_interval` for your sensor.

The following variables are available in the script:
- `self.hass` - The [Home Assistant API](https://www.home-assistant.io/developers/development_hass_object/)
- `self.state` - Change it for update sensor value
- `self.attributes` - Change it for update sensor attributes
- `logger` - A logger to allow you to log messages

Python source code are compiled and cached on load. You need to restart Home Assistant if there were changes in the python source file.

```yaml
sensor:
- platform: python_script
  name: My IP address
  scan_interval: '00:05:00'  # optional
  source: |
    import requests
    r = requests.get('https://api.ipify.org?format=json')
    self.state = r.json()['ip']

- platform: python_script
  name: My DB size
  icon: mdi:database
  unit_of_measurement: MB
  scan_interval: '01:00:00'  # optional
  source: |
    import os
    logger.debug("Update DB size")
    filename = self.hass.config.path('home-assistant_v2.db')
    self.state = round(os.stat(filename).st_size / 1_000_000, 1)
```