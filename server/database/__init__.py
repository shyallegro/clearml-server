from os import getenv

from furl import furl
from jsonmodels import models
from jsonmodels.errors import ValidationError
from jsonmodels.fields import StringField
from mongoengine import register_connection
from mongoengine.connection import get_connection

from config import config
from .defs import Database
from .utils import get_items

log = config.logger("database")

strict = config.get("apiserver.mongo.strict", True)

OVERRIDE_HOST_ENV_KEY = "MONGODB_SERVICE_SERVICE_HOST"

_entries = []


class DatabaseEntry(models.Base):
    host = StringField(required=True)
    alias = StringField()

    @property
    def health_alias(self):
        return "__health__" + self.alias


def initialize():
    db_entries = config.get("hosts.mongo", {})
    missing = []
    log.info("Initializing database connections")

    override_hostname = getenv(OVERRIDE_HOST_ENV_KEY)
    if override_hostname:
        log.info(f"Using override mongodb host {override_hostname}")

    for key, alias in get_items(Database).items():
        if key not in db_entries:
            missing.append(key)
            continue

        entry = DatabaseEntry(alias=alias, **db_entries.get(key))
        if override_hostname:
            entry.host = furl(entry.host).set(host=override_hostname).url

        try:
            entry.validate()
            log.info(
                "Registering connection to %(alias)s (%(host)s)" % entry.to_struct()
            )
            register_connection(alias=alias, host=entry.host)

            _entries.append(entry)
        except ValidationError as ex:
            raise Exception("Invalid database entry `%s`: %s" % (key, ex.args[0]))
    if missing:
        raise ValueError("Missing database configuration for %s" % ", ".join(missing))


def get_entries():
    return _entries


def get_aliases():
    return [entry.alias for entry in get_entries()]


def reconnect():
    for entry in get_entries():
        get_connection(entry.alias, reconnect=True)
