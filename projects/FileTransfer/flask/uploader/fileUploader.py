import os
import requests
import json
import logging
import time

def CreateJsonFile(jsonFileName):
    try:
        if not os.path.isfile(jsonFileName):
            data = {}
            data['upload'] = {
                "path":"C:/fileTransfer/upload",
                "mode":"single"
            }
            data['logging'] = {
                "commandLog":"True",
                "fileLog":"True"
            }
            data['receiver'] = []
            data['receiver'].append({
                "url":"http://127.0.0.1:5000/upload"
            })
            with open(jsonFileName, 'w') as outFile:
                json.dump(data, outFile, indent=4)
            
    except OSError:
        logger.exception(f" !! Error: Creating configuration file. {jsonFileName}")

def HasFolder(directory):
    try:
        if not os.path.exists(directory):
            os.makedirs(directory)
    except OSError:
        logger.exception(f" !! Error: Creating directory. {directory}")

def SendMultiFile(targetUrl, multiFiles):
    # files = open(filePath, 'rb')
    # upload = {'file':files}
    # print(targetUrl)
    # res = requests.post('http://127.0.0.1:5000/upload', files=upload)
    try:
        res = requests.post(targetUrl, files=multiFiles)
        
        # fileName = filePath.split('/')[-1]
        # fileSize = os.path.getsize(filePath)
        
        logger.info(f"[{targetUrl}] >> Completed to transfer the files {res} [Total:{len(multiFiles)}]")
        logger.info("========================================================================================================")
    except Exception as e:
        logger.exception(f" !! Error: Failed to send files to '{targetUrl}'. \n{e}")
    # print(res)

def SendFile(filePath, targetUrl):
    files = open(filePath, 'rb')
    upload = {'file':files}
    
    res = requests.post(targetUrl, files=upload)
     
    fileName = filePath.split('/')[-1]
    fileSize = os.path.getsize(filePath)
    
    logger.info(f"[{targetUrl}] >> Completed to transfer the file {res} [{fileName}, {format(fileSize, ',')} bytes]")
    logger.info("========================================================================================================")

def printLogo():
    os.system("cls")
    logo = """
        ==================================================
        HYUNDAI MOTOR GROUP INNOVATION CENTRE IN SINGAPORE
        FILE TRANSFER - UPLOADER
        ==================================================
        """ 

if __name__ == '__main__':
    
    printLogo()
    
    try:
        currentPath = os.path.dirname(__file__)
        logPath = os.path.join(currentPath, "log")   
        HasFolder(logPath)
        
        # Configuration
        jsonFileName = os.path.join(currentPath, "config.json")
        CreateJsonFile(jsonFileName)
        
        targetList = {}
        isCommandLog = False
        isFileLog = False
        
        with open(jsonFileName, "r") as jsonFile:
            jsonData = json.load(jsonFile)
            
            uploadFilePath = jsonData['upload']['path']
            HasFolder(uploadFilePath)
            
            uploadMode = jsonData['upload']['mode']
            
            targetList = jsonData['receiver']
            
            if jsonData['logging']['commandLog'].upper() == "TRUE":
                isCommandLog = True
            if jsonData['logging']['fileLog'].upper() == "TRUE":
                isFileLog = True
            
        # logger Definition
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s- %(levelname)s - %(message)s')

        # Command Line Log        
        if isCommandLog is True:
            streamHandler = logging.StreamHandler()
            streamHandler.setFormatter(formatter)
            logger.addHandler(streamHandler)
        
        # file log
        if isFileLog is True:
            fileHandler = logging.FileHandler(os.path.join(logPath, f"{time.strftime('%Y%m%d')}_fileLog.log"))
            fileHandler.setFormatter(formatter)
            logger.addHandler(fileHandler)
        
    except Exception as e:
        print(e)
        
    #######################################################################################################
    # Main Logic Call (Each receiver & Files)
    #######################################################################################################
    if uploadMode.upper() == "SINGLE":
        for targetUrl in targetList:
            for (root, directories, files) in os.walk(uploadFilePath):
                for file in files:
                    filePath = os.path.join(root, file)
                    SendFile(filePath=filePath, targetUrl=targetUrl['url'])
    else:
        multiFiles = []
        for targetUrl in targetList:
            for (root, directories, files) in os.walk(uploadFilePath):
                for file in files:
                    filePath = os.path.join(root, file)      
                    multiFiles.append(('file', open(filePath, 'rb')))   # make multifiles variable as tuple
                    
            SendMultiFile(targetUrl=targetUrl['url'], multiFiles=multiFiles)
    #######################################################################################################    