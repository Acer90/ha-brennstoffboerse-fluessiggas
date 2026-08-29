from __future__ import annotations

from datetime import timedelta

DOMAIN = "brennstoffboerse_fluessiggas"

CONF_REGION = "region"
CONF_VOLUME_LITERS = "volume_liters"

DEFAULT_VOLUME_LITERS = 3000
ALLOWED_VOLUMES_LITERS: tuple[int, ...] = (1000, 3000, 5000)

URL = "https://brennstoffboerse.de/fluessiggas/fluessiggas-tagespreise.html"

UPDATE_INTERVAL = timedelta(hours=6)
