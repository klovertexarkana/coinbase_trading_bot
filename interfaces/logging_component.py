import logging


class Logging(logging.Logger):
    def __init__(self, name):
        super().__init__(name)

        self.logger = logging.getLogger()
        self.logger.setLevel(logging.DEBUG)
        # formatter sets the basic format of the logs
        self.formatter = logging.Formatter('%(asctime)s %(levelname)s :: %(message)s')
        # the stream_handler object sends logs to sys.stdout, sys.stderr or any file-like object, the formatter is
        # passed to it
        self.stream_handler = logging.StreamHandler()
        self.stream_handler.setFormatter(self.formatter)
        # curious if you needed to set the level for both the logger and the stream_handler, what would happen if they
        # were set to different levels?
        self.stream_handler.setLevel(logging.INFO)

        # because I do not want to use a visual interface I want to be able to delete old logs
        self.file_handler = logging.FileHandler('info.log', mode='w')
        # I assume formatter needs to be passed so the output to the file is the same that gets sent to the console
        self.file_handler.setFormatter(self.formatter)
        # we want more info sent to the logs than the terminal
        self.file_handler.setLevel(logging.DEBUG)

        self.logger.addHandler(self.stream_handler)
        self.logger.addHandler(self.file_handler)


def get_logger(name=None):
    """Provides logger for import to other components/modules."""
    logging_class = logging.getLoggerClass()  # store the current logger factory for later
    logging._acquireLock()  # use the global logging lock for thread safety
    try:
        logging.setLoggerClass(Logging)  # temporarily change the logger factory
        my_logger = logging.getLogger(name)
        logging.setLoggerClass(logging_class)  # be nice, revert the logger factory change
        return my_logger
    finally:
        logging._releaseLock()


logger = get_logger(__name__)
