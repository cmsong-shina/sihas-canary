class PacketSizeError(Exception):
    """Not excpeted length"""

    def __init__(self, expect: int, actual: int) -> None:
        self._expect = expect
        self._actual = actual

    def __str__(self) -> str:
        return f"packet size does not match: expect {self._expect}, but actual {self._actual}, may modbus not enabled"


class ModbusNotEnabledError(Exception):
    """Modbus not enabled"""

    def __init__(self, device=None) -> None:
        self._device = device

    def __str__(self) -> str:
        detail = f": {self._device}" if self.device else ""
        return f"modbus does not enabled check in the app about device" + detail


class InitializingError(Exception):
    """Error during setup platform"""

    def __init__(self, device_type, ip, message) -> None:
        self._device_type = device_type
        self._ip = ip
        self._message = message

    def __str__(self) -> str:
        return f"Error during initializing <{self._device_type}, {self._ip}>: device does not responsed. be sure IP is correct and restart HA to load HCM"
