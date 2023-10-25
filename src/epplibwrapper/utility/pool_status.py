class PoolStatus:
    """A list of Booleans to keep track of Pool Status.
    
    pool_running -> bool: Tracks if the pool itself is active or not.
    connection_success -> bool: Tracks if connection is possible with the registry.
    pool_hanging -> pool: Tracks if the pool has exceeded its timeout period.
    """

    def __init__(self):
        self.pool_running = False
        self.connection_success = False
        self.pool_hanging = False
