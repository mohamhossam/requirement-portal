"""Which service and release this process is, for metrics, traces and `/health`."""

from importlib.metadata import version

# The installed package's version, which a release tag must match (ADR-0108).
APPLICATION_VERSION = version("smb-requirement-agent")
SERVICE_NAME = "requirement-portal"
