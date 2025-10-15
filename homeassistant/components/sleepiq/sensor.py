"""Support for SleepIQ sensors."""
from . import SleepIQEntity, SleepIQData
from .const import DOMAIN, SENSOR_TYPES, SIDES, SLEEP_NUMBER
from ...core import HomeAssistant

ICON = "mdi:bed"


def setup_platform(hass: HomeAssistant, config, add_entities, discovery_info=None):
    """Set up the SleepIQ sensors."""
    _ = config  # Unused.
    if discovery_info is None:
        return

    data: SleepIQData = hass.data[DOMAIN]
    data.update_account_from_network()

    dev = []
    for bed_id, bed in data.beds.items():
        for side in SIDES:
            if getattr(bed, side) is not None:
                dev.append(SleepNumberSensor(data, bed_id, side))
    add_entities(dev)


class SleepNumberSensor(SleepIQEntity):
    """Implementation of a SleepIQ SleepNumber sensor."""

    def __init__(self, sleepiq_data, bed_id, side):
        """Initialize the sensor."""
        SleepIQEntity.__init__(self, sleepiq_data, bed_id, side)

        self._state = None
        self.type = SLEEP_NUMBER
        self._name = SENSOR_TYPES[self.type]

        self.update()

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the latest data from SleepIQ and updates the states."""
        SleepIQEntity.update(self)
        self._state = self.side.sleep_number
