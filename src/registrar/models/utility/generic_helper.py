"""This file contains general purpose helpers that don't belong in any specific location"""

import time
import logging


logger = logging.getLogger(__name__)


class Timer:
    """
    This class is used to measure execution time for performance profiling.
    __enter__ and __exit__ is used such that you can wrap any code you want
    around a with statement. After this exits, logger.info will print
    the execution time in seconds.

    Note that this class does not account for general randomness as more
    robust libraries do, so there is some tiny amount of latency involved
    in using this, but it is minimal enough that for most applications it is not
    noticable.

    Usage:
    with Timer():
        ...some code
    """

    def __enter__(self):
        """Starts the timer"""
        self.start = time.time()
        # This allows usage of the instance within the with block
        return self

    def __exit__(self, *args):
        """Ends the timer and logs what happened"""
        self.end = time.time()
        self.duration = self.end - self.start
        logger.info(f"Execution time: {self.duration} seconds")
