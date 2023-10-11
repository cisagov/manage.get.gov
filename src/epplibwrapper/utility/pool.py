from asyncio import Queue
from queue import Empty
import logging
from epplibwrapper.utility.connector import EPPConnector
from socketpool.pool import ConnectionPool
logger = logging.getLogger(__name__)

class EppConnectionPool():
    def __init__(self, **options):
        logger.debug("EppConnectionPool() -> init was successful")
        self.pool = ConnectionPool(
            factory=EPPConnector,
            options=options
        )
        logger.debug("EppConnectionPool() -> pool created")
        self.service = EppPoolService()
        self.service.start()
        self.command_queue = Queue()

    def runpool(self):
        logger.debug("EppConnectionPool() -> in run pool")
        while True:
            command_exists = True
            # This is the exit condition
            try:
                data = self.command_queue.get()
            except Empty:
                logger.debug("EppConnectionPool() -> empty queue")
                command_exists = False

            if command_exists:
                try:
                    with self.pool.connection() as conn:
                        logger.info("conn: pool size: %s" % self.pool.size)
                        data = conn.send(data)
                        logger.info(f"conn: pool got {data}")
                finally:
                    self.command_queue.task_done()

class EppPoolService():
    def __init__(self):
        self.running = False

    def start(self):
        pass

    def run(self):
        pass

    def handle(self, sock, address):
        pass

    def stop(self):
        self.running = False
