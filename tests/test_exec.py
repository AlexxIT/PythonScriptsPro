from custom_components.python_script import execute_script

hass = type("", (), {})
logger = type("", (), {})


def test_issue6():
    # https://github.com/AlexxIT/PythonScriptsPro/issues/6
    source = """def foobar():
    pass
foobar()
(lambda: foobar())()
out = 123
"""
    code = compile(source, "<string>", "exec")
    result = execute_script(hass, {}, logger, code)
    assert result == {"out": 123}


def test_issue18():
    # https://github.com/AlexxIT/PythonScriptsPro/issues/18
    source = """import requests
def foobar():
    from requests import session
foobar()
out = 123
"""
    code = compile(source, "<string>", "exec")
    result = execute_script(hass, {}, logger, code)
    assert result == {"out": 123}


def test_issue23():
    # https://github.com/AlexxIT/PythonScriptsPro/issues/23
    source = """from .secrets import get_secret
out = 123
"""
    code = compile(source, "<string>", "exec")
    result = execute_script(hass, {}, logger, code)
    assert result == {
        "error": "No module named 'custom_components.python_script.secrets'"
    }
