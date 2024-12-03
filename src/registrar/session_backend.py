from django.contrib.sessions.backends.db import SessionStore as cacheSessionStore
import logging

logger = logging.getLogger(__name__)


class SessionStore(cacheSessionStore):
    def __init__(self, session_key=None):
        logger.info("SESSION: Custom SessionStore initialized")
        super().__init__(session_key=session_key)

    def load(self):
        session_data = super().load()
        if self.session_key:
            logger.info(f"SESSION LOAD: key={self.session_key}")
        logger.info(f"SESSION LOAD: data={session_data}")
        # logger.info(f"SESSION LOAD: data={dict(self)}")
        return session_data

    # def save(self, must_create=False):
    #     super().save(must_create)

    def delete(self, session_key=None):
        if self.session_key:
            logger.info(f"SESSION DELETE: key={self.session_key}")
        else:
            logger.info("SESSION DELETE")
        # logger.info(f"SESSION DELETE: data={dict(self)}")
        super().delete(session_key)

    # def __setitem__(self, key, value):
    #     logger.info(f"Adding to session: {key} = {value}")
    #     super().__setitem__(key, value)

    # def __getitem__(self, key):
    #     value = super().__getitem__(key)
    #     logger.info(f"Accessed session key: {key}. Value: {value}")
    #     return value

    def flush(self):
        if self.session_key:
            logger.info(f"SESSION FLUSH: key={self.session_key}")
        else:
            logger.info("SESSION FLUSH")
