class PoolStatus:
    """A list of Booleans to keep track of Pool Status"""
    def __init__(self):
        self.pool_running = False
        self.connection_success = False
        self.pool_hanging = False
