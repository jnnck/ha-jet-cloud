"""Constants for the JET Cloud integration."""

from datetime import timedelta

DOMAIN = "jet_cloud"

CONF_PASSWORD_HASH = "password_hash"
CONF_HOST = "host"
CONF_PROJECT_TYPE = "project_type"

# The cloud itself only refreshes every 1-5 minutes.
UPDATE_INTERVAL = timedelta(minutes=2)
