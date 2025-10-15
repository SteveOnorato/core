"""Support for SleepIQ from SleepNumber."""
from datetime import timedelta
import logging
from typing import List, Dict, Optional

from sleepyq import Sleepyq, Bed, FoundationStatus, SideStatus
import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from .const import DOMAIN
from ...core import HomeAssistant

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(DOMAIN): vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config):
    """Set up the SleepIQ component.

    Will automatically load sensor components to support
    devices discovered on the account.
    """
    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]
    client = Sleepyq(username, password)
    try:
        data: SleepIQData = SleepIQData(client)
        data.update_account_from_network()
    except ValueError:
        message = """
            SleepIQ failed to login, double check your username and password"
        """
        _LOGGER.error(message)
        return False

    # Make our single SleepIQData instance available to our other modules.
    hass.data[DOMAIN] = data
    discovery.load_platform(hass, "sensor", DOMAIN, {}, config)
    discovery.load_platform(hass, "binary_sensor", DOMAIN, {}, config)
    discovery.load_platform(hass, "cover", DOMAIN, {}, config)

    return True


class SleepIQData:
    """ Stores the latest responses from SleepIQ for the entire account."""

    beds: Dict[str, Bed]
    foundation_status: Optional[FoundationStatus]  # Can be None when there was a network error.

    def __init__(self, client: Sleepyq):
        """Initialize the data object."""
        self._client: Sleepyq = client
        self.update_account_from_network()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update_account_from_network(self):
        """Get the latest data from SleepIQ."""
        _LOGGER.debug("Updating SleepIQ data from network.")
        beds: List[Bed] = self._client.beds_with_sleeper_status()
        self.beds = {bed.bed_id: bed for bed in beds}
        self.foundation_status = self._client.foundation_status()
        _LOGGER.debug("Done updating SleepIQ data from network.")


class SleepIQEntity(Entity):
    """Implementation of a single SleepIQ entity."""

    def __init__(self, sleepiq_data: SleepIQData, bed_id, side):
        """Initialize the sensor."""
        self._bed_id = bed_id
        # Must match the names in Bed: "left" or "right" only.
        self._side = side
        self.sleepiq_data = sleepiq_data

        # Filled in self.update.
        self.side: Optional[SideStatus] = None
        self.bed: Optional[Bed] = None

        # added by subclass
        self._name = None
        self.type = None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"SleepNumber {self.bed.name} {self.side.sleeper.first_name} {self._name}"

    @property
    def foundation_status(self) -> Optional[FoundationStatus]:
        return self.sleepiq_data.foundation_status

    def update(self):
        """Get the latest data from SleepIQ (if not fresh) and update the states."""

        # Call the API for new sleepiq data. Each sensor will re-trigger this
        # same exact call, but that's fine. We cache results for a short period
        # of time to prevent hitting API limits.
        self.sleepiq_data.update_account_from_network()

        self.bed = self.sleepiq_data.beds[self._bed_id]
        self.side = getattr(self.bed, self._side)
