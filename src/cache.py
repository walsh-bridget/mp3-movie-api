import json
import logging

import fakeredis

logger = logging.getLogger(__name__)


class MovieCache:
    def __init__(self):
        self.client = fakeredis.FakeRedis(decode_responses=True)

    def make_key(self, limit):
        return f"movies:limit:{limit}"

    def get(self, limit):
        """Return the cached response dictionary, or None."""
        # gets key 
        key = self.make_key(limit)
        cached_response = self.client.get(key)
        # logs HIT or MISS
        if cached_response is None:
            logger.debug("Cache MISS: %s", key)
            return None

        logger.debug("Cache HIT: %s", key)
        return json.loads(cached_response)

    def set(self, limit, response):
        """Cache the response dictionary for 90 seconds."""
        key = self.make_key(limit)
        self.client.set(key, json.dumps(response), ex=90)

    def invalidate(self):
        """Remove all cached movie retrievals."""
        # clears dedicated FakeRedis cache
        self.client.flushdb()
        logger.debug("Invalidated movie cache")
