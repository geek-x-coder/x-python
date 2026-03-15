import sys
import os
import json

from modules.xLogger.xLogger import Logger

class Configuration :
    def __init__(self, jsonFilePath, logPath=os.path.dirname(__file__)) :
        
        # self.application = Application()
        self.jsonFilePath = jsonFilePath
        
        data = {}
        self.createDefault(data)
        
        # self.logger = Logger(True, True, logPath)
        self.logger = Logger(isDisplayLog=True)
        
    def getMethodName(self):
        return f"{self.__class__.__name__}.{sys._getframe(1).f_code.co_name}"

    def load(self):
        jsonData = ""
        
        with open(self.jsonFilePath, 'r') as jsonFile:
            jsonData = json.load(jsonFile)
            
        self.logger.info(f"Load Configuration >> path={self.jsonFilePath}")
        return jsonData

    def createDefault(self, data):
        try:
            if not os.path.isfile(self.jsonFilePath) : 
                with open(self.jsonFilePath, 'w') as outFile:
                    json.dump(data, outFile, indent=4)
                    
        except Exception as e:
            self.logger.exception(f"An exception occurred >> {self.getMethodName()} \n {e}")
            

        