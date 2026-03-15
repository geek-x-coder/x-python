import time
from modules.xLogger.xLogLevel import LogLevel

class LogWriter:
    def __init__ (self, isDisplayLog=False):
        self.isDisplayLog = isDisplayLog
    
    def printLog(self, msg, level, end="\n"):
        if(self.isDisplayLog == True):
            if level == LogLevel.info:
                print(f"\r\033[92m{time.strftime('%Y-%m-%d %H:%M:%S')} \033[97m>> {msg} \033[0m", end=end)
                
            elif level == LogLevel.warning :
                print(f"\r\033[33m{time.strftime('%Y-%m-%d %H:%M:%S')} !! {msg} \033[0m", end=end)
            else:
                print(f"\r\033[31m{time.strftime('%Y-%m-%d %H:%M:%S')} !! {msg} \033[0m", end=end)
                

        else:
            if level == LogLevel.warning :
                print(f"\r\033[33m{time.strftime('%Y-%m-%d %H:%M:%S')} !! {msg} \033[0m", end=end)
            elif level == LogLevel.error or level == LogLevel.exception :
                print(f"\r\033[31m{time.strftime('%Y-%m-%d %H:%M:%S')} !! {msg} \033[0m", end=end)