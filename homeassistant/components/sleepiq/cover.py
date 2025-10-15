"""Support for SleepIQ bed foundation head/foot incline."""
import logging
from typing import Optional, Any

from . import SleepIQEntity, SleepIQData
from .const import DOMAIN, SENSOR_TYPES, SIDES, FOUNDATION_HEAD, LEFT
from ..cover import CoverEntity, SUPPORT_SET_POSITION, SUPPORT_CLOSE, SUPPORT_STOP, SUPPORT_OPEN, ATTR_POSITION, \
    DEVICE_CLASS_SHADE
from ...core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass: HomeAssistant, config, add_entities, discovery_info=None):
    """Set up the SleepIQ cover entities."""
    _ = config  # Unused.
    if discovery_info is None:
        return

    data: SleepIQData = hass.data[DOMAIN]
    data.update_account_from_network()

    dev = []
    for bed_id, bed in data.beds.items():
        for side in SIDES:
            if getattr(bed, side) is not None:
                dev.append(SleepNumberCover(data, bed_id, side))
    add_entities(dev)


class SleepNumberCover(SleepIQEntity, CoverEntity):
    """Implementation of a SleepIQ cover."""

    _position: Optional[int] = None
    _previous_position: Optional[int] = None
    _is_moving: bool = False

    def __init__(self, sleepiq_data: SleepIQData, bed_id: str, side: str):
        """Initialize the sensor."""
        SleepIQEntity.__init__(self, sleepiq_data, bed_id, side)

        self.type = FOUNDATION_HEAD
        self._name = SENSOR_TYPES[self.type]

        self.update()

    @property
    def current_cover_position(self):
        """Return current position of the cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._position

    @property
    def is_opening(self):
        """Return if the cover is opening (increasing) or not."""
        return self._is_moving and (self._previous_position < self._position)

    @property
    def is_closing(self):
        """Return if the cover is closing (decreasing) or not."""
        return self._is_moving and (self._previous_position > self._position)

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        return self._position == 0

    @property
    def device_class(self) -> Optional[str]:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_SHADE

    @property
    def supported_features(self) -> Optional[int]:
        """Flag supported features."""
        # Pretending to be a WindowCovering, since it seems to be the only way to surface this in HomeKit as per
        # homeassistant/components/homekit/accessories.py:158
        # if device_class in (DEVICE_CLASS_GARAGE, DEVICE_CLASS_GATE) and features & (
        #     cover.SUPPORT_OPEN | cover.SUPPORT_CLOSE
        # ):
        #     a_type = "GarageDoorOpener"
        # elif features & cover.SUPPORT_SET_POSITION:
        #     a_type = "WindowCovering"
        # elif features & (cover.SUPPORT_OPEN | cover.SUPPORT_CLOSE):
        #     a_type = "WindowCoveringBasic"
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION | SUPPORT_STOP

    def open_cover(self, **kwargs: Any) -> None:
        _LOGGER.info("open_cover")
        self.call_service_to_set_position(100)

    def close_cover(self, **kwargs: Any) -> None:
        _LOGGER.info("close_cover")
        self.call_service_to_set_position(0)

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        _LOGGER.info("set_cover_position")
        if ATTR_POSITION in kwargs:
            self.call_service_to_set_position(kwargs[ATTR_POSITION])

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        _LOGGER.info("stop_cover")
        # TODO: provide a method on SleepIQData to expose and throttle this.
        self.sleepiq_data._client.stop_motion(self.side, self._bed_id)

    def call_service_to_set_position(self, position: int):
        _LOGGER.info("call_service_to_set_position(%d)", position)
        # TODO: provide a method on SleepIQData to expose and throttle this.
        self.sleepiq_data._client.set_foundation_position(self._side, 'h', position, self._bed_id)

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return "mdi:bed"

    def update(self):
        """Get the latest data from SleepIQ and update the states."""
        SleepIQEntity.update(self)
        if self.foundation_status is None:
            return
        side_str = 'Left' if self._side is LEFT else 'Right'
        head_or_foot = 'Head'
        position_attr_name = f'fs{side_str}{head_or_foot}Position'  # example: fsLeftHeadPosition
        motor_attr_name = f'fs{side_str}{head_or_foot}ActuatorMotorStatus'  # example: fsLeftHeadActuatorMotorStatus
        position_percentage_hex = getattr(self.foundation_status, position_attr_name)
        motor_status_hex = getattr(self.foundation_status, motor_attr_name)
        motor_status = int(motor_status_hex, 16)
        new_position = int(position_percentage_hex, 16)

        # Avoid overwriting previous position unless there really is a new current position.
        # Since we throttle the actual API calls, we may see the same data multiple times.
        if self._position != new_position:
            self._previous_position = self._position
            self._position = new_position
        self._is_moving = ((motor_status & 1) == 1)
        _LOGGER.debug("%s: %s (moving=%s, prev=%s)", position_attr_name, self._position, self._is_moving,
                      self._previous_position)
