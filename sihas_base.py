import logging
import socket
from typing import Final, List, Optional

from homeassistant.helpers.entity import Entity

from .errors import ModbusNotEnabledError
from .packet_builder import packet_builder as pb
from .sender import send
from .util import Debouncer

_LOGGER = logging.getLogger(__name__)

DEFAULT_DEBOUNC_DURATION: Final = 5


class SihasBase:
    """Representation of an base class of Sihas device

    And also provider basic interface Poll and Command to communicate to device.

    Attributes
    ----------
    ip : str
        ip address of device. check it in the router's page, not in the App(it
        may not correct)
    mac : str
        mac address of device
    device_type : str
        type of device as string, like `ACM` or `STM`
    config : int
        `CFG` of device, check in `장치정보` page of App
    """

    def __init__(
        self,
        ip: str,
        mac: str,
        device_type: str,
        config: int,
    ) -> None:
        # init mandatory sihas value
        self.ip = ip
        self.mac = mac
        self.device_type = device_type
        self.config = config

        self._attr_available = False

    def poll(self) -> Optional[List[int]]:
        """Read Holding Registers and return registers.

        If failed return None. So use this function with walrus operator, like below.

        ```python
        if registers := self.poll():
            self.registers = registers
        ```
        """

        try:
            req = pb.poll()
            resp = send(req, self.ip, retry=3)
            regs = pb.extract_registers(resp)
            self._attr_available = True
            return regs

        except ModbusNotEnabledError:
            _LOGGER.warn("modbus <%s, %s>", self.device_type, self.ip)

        except socket.timeout:
            _LOGGER.info("timeout during update on <%s, %s>", self.device_type, self.ip)

        except Exception as err:
            _LOGGER.warn(
                "unhandled exception: %s during update on <%s, %s>",
                err,
                self.device_type,
                self.ip,
            )

        # if exception catched
        self._attr_available = False
        _LOGGER.info(f"device set to not available <{self.device_type, self.ip}>")
        return None

    def command(self, idx, val) -> bool:
        try:
            req = pb.command(idx, val)
            if send(req, self.ip, retry=3):
                self._attr_available = True
                return True

        except ModbusNotEnabledError:
            _LOGGER.warn("modbus <%s, %s>", self.device_type, self.ip)

        except socket.timeout:
            _LOGGER.info("timeout during command on <%s, %s>", self.device_type, self.ip)

        except Exception as err:
            _LOGGER.warn(
                "unhandled exception: %s during command on <%s, %s>",
                err,
                self.device_type,
                self.ip,
            )
        self._attr_available = False
        return False


class SihasEntity(SihasBase, Entity):
    """Provide common HA feature, such as default uid generate

    _attr_unique_id
        combination of `device_type`, `mac` and `sub-device-number`(if needed).
        for example:
            - `ACM-12:34:56:78:90:ab`: ACM
            - `STM-12:34:56:78:90:ab-1`: STM, first switch
            - `STM-12:34:56:78:90:ab-2`: STM, secound switch
    """

    def __init__(
        self,
        ip: str,
        mac: str,
        device_type: str,
        config: int,
        uid: str = None,
    ) -> None:
        super().__init__(
            ip,
            mac,
            device_type,
            config,
        )

        # init optional value
        self._attr_unique_id = uid if uid else f"{self.device_type}-{self.mac}"

        # init empty value
        self._attributes = {}
        self._state = None

    @property
    def extra_state_attributes(self):
        return self._attributes

    def update(self):
        raise NotImplementedError(f"update method does not implemented for {self.device_type}")


class SihasProxy(SihasBase):
    """Provide proxy features

    Note
    ----
    Virtual Entity, which *has* SihasProxy instance, must follow below requirements:
        - Set `_attr_unique_id` when initializing.
        - Sync `_attr_available` after update.

    Attributes
    ----------
    registers : List[int]
        hold registers to update whole state.
    _proxy_updater: Debouncer
        Debouncer to prevent poll many times at once about one device, because of
        sub-device instances.
    """

    def __init__(
        self,
        ip: str,
        mac: str,
        device_type: str,
        config: int,
    ) -> None:
        super().__init__(
            ip,
            mac,
            device_type,
            config,
        )
        self.registers = [0] * 64
        # self.proxy_available = False
        self._proxy_updater = Debouncer(DEFAULT_DEBOUNC_DURATION, self._internal_update)

    def _internal_update(self):
        if registers := self.poll():
            self.registers = registers

    def update(self, force=False):
        """Polling via debouncer.

        Parameters
        ----------
        force
            Forcely update without debouncer.
        """
        self._proxy_updater.run(force)

    def command(self, idx, val) -> None:
        """Excute Command and additional Poll to avoid debouncer"""
        super().command(idx, val)
        self._internal_update()

    def get_sub_entities(self) -> List[Entity]:
        """Generate sub-instances"""
        raise NotImplementedError()
