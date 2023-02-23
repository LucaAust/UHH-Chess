import logging
from pathlib import Path
from typing import Union
from logging.handlers import TimedRotatingFileHandler


class AstlLogger:
    def __init__(self, log_dir: Path, loglevel: int, log_to_stdout: bool = False, log_backup_count: Union[int, None] = 7):
        self.log_dir = log_dir / 'log'
        self.log_level = loglevel
        self.log_name = str(log_dir.absolute().name).replace(' ', '_')
        self.log_to_stdout = log_to_stdout
        self.log_backup_count = log_backup_count
        
        self.__setup_logger()

    def __setup_logger(self):
        print(f"self.log_backup_count: {self.log_backup_count}")
        logger = logging.getLogger()
        logger.setLevel(self.log_level)
        log_formatter = logging.Formatter("%(asctime)s [%(levelname)-5.5s] [%(filename)s:%(lineno)s] [%(funcName)s()] %(message)s")
        
        # create log dir if not exist
        if not self.log_dir.exists():
            self.log_dir.mkdir(parents=True)

        # add handler to log into stdout
        if self.log_to_stdout:
            print(f"Log to stdout is active.")
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(log_formatter)
            stream_handler.setLevel(self.log_level)
            logger.addHandler(stream_handler)

        print(self.log_dir / f"{self.log_name}.log")
        # add default log with file rotation
        file_handler = TimedRotatingFileHandler(
            filename=self.log_dir / f"{self.log_name}.log", when='midnight', backupCount=self.log_backup_count)
        file_handler.setFormatter(log_formatter)
        file_handler.setLevel(self.log_level)
        logger.addHandler(file_handler)
                
        # add error log
        error_file_handler = TimedRotatingFileHandler(
            filename=self.log_dir / f'{self.log_name}_error.log', when='midnight', backupCount=self.log_backup_count)
        error_file_handler.setFormatter(log_formatter)
        error_file_handler.setLevel(logging.ERROR)
        logger.addHandler(error_file_handler)
        
            
if __name__ == "__main__":
    AstlLogger(Path(), logging.INFO, True)
    log = logging.getLogger()
    log.info("Hallo")
    log.debug("Hallo")
    log.error("Hallo")
    log.warning("Hallo")
