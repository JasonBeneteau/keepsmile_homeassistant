import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "custom_components" / "keepsmile" / "bjled.py"


class DummyBLEDevice:
    def __init__(self, name="Test", address="AA:BB:CC:DD:EE:FF"):
        self.name = name
        self.address = address


@pytest.fixture
def bjled_module(monkeypatch):
    homeassistant = types.ModuleType("homeassistant")
    components = types.ModuleType("homeassistant.components")
    bluetooth = types.ModuleType("homeassistant.components.bluetooth")
    bluetooth.async_ble_device_from_address = lambda hass, address: DummyBLEDevice(address=address)
    components.bluetooth = bluetooth

    light = types.ModuleType("homeassistant.components.light")
    light.ColorMode = types.SimpleNamespace(RGB="rgb", BRIGHTNESS="brightness", ONOFF="onoff")

    exceptions = types.ModuleType("homeassistant.exceptions")
    class ConfigEntryNotReady(Exception):
        pass
    exceptions.ConfigEntryNotReady = ConfigEntryNotReady

    const = types.ModuleType("homeassistant.const")
    const.CONF_MAC = "mac"

    monkeypatch.setitem(sys.modules, "homeassistant", homeassistant)
    monkeypatch.setitem(sys.modules, "homeassistant.components", components)
    monkeypatch.setitem(sys.modules, "homeassistant.components.bluetooth", bluetooth)
    monkeypatch.setitem(sys.modules, "homeassistant.components.light", light)
    monkeypatch.setitem(sys.modules, "homeassistant.exceptions", exceptions)
    monkeypatch.setitem(sys.modules, "homeassistant.const", const)

    bleak = types.ModuleType("bleak")
    backends = types.ModuleType("bleak.backends")
    device = types.ModuleType("bleak.backends.device")
    device.BLEDevice = DummyBLEDevice
    service = types.ModuleType("bleak.backends.service")
    service.BleakGATTCharacteristic = object
    service.BleakGATTServiceCollection = object
    exc = types.ModuleType("bleak.exc")
    class BleakDBusError(Exception):
        pass
    exc.BleakDBusError = BleakDBusError
    bleak.backends = backends
    backends.device = device
    backends.service = service
    bleak.exc = exc

    retry_connector = types.ModuleType("bleak_retry_connector")
    retry_connector.BLEAK_RETRY_EXCEPTIONS = ()
    retry_connector.BleakClientWithServiceCache = object
    retry_connector.BleakNotFoundError = type("BleakNotFoundError", (Exception,), {})
    retry_connector.establish_connection = lambda *args, **kwargs: None

    cheshire = types.ModuleType("cheshire")
    compiler_module = types.ModuleType("cheshire.compiler")
    compiler_module.compiler = types.SimpleNamespace(StateCompiler=object)
    state_module = types.ModuleType("cheshire.compiler.state")

    class LightState:
        def __init__(self):
            self._commands = []

        def update(self, command):
            self._commands.append(command)

    state_module.LightState = LightState
    generic_module = types.ModuleType("cheshire.generic")
    command_module = types.ModuleType("cheshire.generic.command")
    class DummyCommand:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
    for name in ["SwitchCommand", "BrightnessCommand", "RGBCommand", "EffectCommand"]:
        setattr(command_module, name, DummyCommand)

    class EffectMeta(type):
        def __iter__(cls):
            yield cls("dummy")

    class Effect(metaclass=EffectMeta):
        def __init__(self, value):
            self.value = value

    command_module.Effect = Effect

    hal = types.ModuleType("cheshire.hal")
    devices_module = types.ModuleType("cheshire.hal.devices")
    devices_module.device_profile_from_ble_device = lambda device: None

    comm_module = types.ModuleType("cheshire.communication")
    transmitter_module = types.ModuleType("cheshire.communication.transmitter")
    transmitter_module.Transmitter = object

    monkeypatch.setitem(sys.modules, "bleak", bleak)
    monkeypatch.setitem(sys.modules, "bleak.backends", backends)
    monkeypatch.setitem(sys.modules, "bleak.backends.device", device)
    monkeypatch.setitem(sys.modules, "bleak.backends.service", service)
    monkeypatch.setitem(sys.modules, "bleak.exc", exc)
    monkeypatch.setitem(sys.modules, "bleak_retry_connector", retry_connector)
    monkeypatch.setitem(sys.modules, "cheshire", cheshire)
    monkeypatch.setitem(sys.modules, "cheshire.compiler", compiler_module)
    monkeypatch.setitem(sys.modules, "cheshire.compiler.compiler", compiler_module.compiler)
    monkeypatch.setitem(sys.modules, "cheshire.compiler.state", state_module)
    monkeypatch.setitem(sys.modules, "cheshire.generic", generic_module)
    monkeypatch.setitem(sys.modules, "cheshire.generic.command", command_module)
    monkeypatch.setitem(sys.modules, "cheshire.hal", hal)
    monkeypatch.setitem(sys.modules, "cheshire.hal.devices", devices_module)
    monkeypatch.setitem(sys.modules, "cheshire.communication", comm_module)
    monkeypatch.setitem(sys.modules, "cheshire.communication.transmitter", transmitter_module)

    spec = importlib.util.spec_from_file_location("bjled_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_detect_model_raises_config_entry_not_ready_for_unknown_profile(bjled_module):
    async def run_test():
        with pytest.raises(bjled_module.ConfigEntryNotReady):
            bjled_module.BJLEDInstance("AA:BB:CC:DD:EE:FF", False, 0, object())

    asyncio.run(run_test())
