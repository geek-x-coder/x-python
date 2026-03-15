from modules.xLogger.xLogWriter import LogWriter, LogLevel


class Logger :
    def __init__(self, isDisplayLog=False) :
        self.logWriter = LogWriter(isDisplayLog)
        
    def info(self, msg, end="\n"):
        self.logWriter.printLog(msg, LogLevel.info, end)
        
    def warning(self, msg, end="\n"):
        self.logWriter.printLog(msg, LogLevel.warning, end)
        
    def error(self, msg, end="\n"):
        self.logWriter.printLog(msg, LogLevel.error, end)
        
    def exception(self, msg, end="\n"):
        self.logWriter.printLog(msg, LogLevel.exception, end)    
        