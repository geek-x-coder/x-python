import os
import json
import time
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse
import uvicorn
import shutil
from tqdm import tqdm

# run : uvicorn {filename}:app --reload
app = FastAPI()

def CreateJsonFile(jsonFilePath):
    try:
        if not os.path.isfile(jsonFilePath):
            data = {}
            data['download'] = {
                "path":"./download",
                "mode":"multi"
            }
            with open(jsonFilePath, 'w') as outFile:
                json.dump(data, outFile, indent=4)
            
    except OSError:
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} !! Error: Creating File. {jsonFilePath}")

def HasFolder(directory):
    try:
        if not os.path.exists(directory):
            os.makedirs(directory)
    except OSError:
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} !! Error: Creating directory. {directory}")

def printLogo():
    os.system("cls")
    logo = """
        ==================================================
        HYUNDAI MOTOR GROUP INNOVATION CENTRE IN SINGAPORE
        FILE TRANSFER - DOWNLOADER
        ==================================================
        """ 

# HTTP POST방식으로 전송된 파일을 저장
@app.post('/fileTransfer')
async def FileReceive(files:list[UploadFile] = File(description="Multiple files as Uploadfile"), ):
    
    currentPath = os.path.dirname(__file__)
    jsonFilePath = os.path.join(currentPath, "config.json")
    
    CreateJsonFile(jsonFilePath=jsonFilePath)
    with open(jsonFilePath, "r") as jsonFile:
        jsonData = json.load(jsonFile)
        
        filePath = jsonData['download']['path']
        downloadMode = jsonData['download']['mode']
    
    HasFolder(filePath)
    
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} >> Download path : {filePath}")
    
    for file in files:
        fileFullPath = os.path.join(filePath, file.filename)
        with open(fileFullPath, "wb") as f:
            shutil.copyfileobj(file.file, f)

    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} >> Completed to receive the files [Total:{len(files)}]")
    
    return {"result":200}

if __name__ == '__main__':
    
    printLogo()
    
    # currentPath = os.path.dirname(__file__)
    # jsonFilePath = os.path.join(currentPath, "config.json")
    
    # CreateJsonFile(jsonFilePath=jsonFilePath)
    # with open(jsonFilePath, "r") as jsonFile:
    #     jsonData = json.load(jsonFile)
        
    #     filePath = jsonData['download']['path']
    #     downloadMode = jsonData['download']['mode']
    
    # HasFolder(filePath)
    
    # print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} >> Download path : {filePath}")
    # print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} >> Mode : {downloadMode}")
    
    uvicorn.run("receiver:app")
    

