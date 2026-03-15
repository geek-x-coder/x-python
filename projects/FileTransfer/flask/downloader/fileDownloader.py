from flask import request
from flask import Flask
from werkzeug.utils import secure_filename
import os
import json
import time
from tqdm import tqdm


app = Flask(__name__)
# bp = Blueprint('image', __name__, url_prefix='/image')

def CreateJsonFile(jsonFilePath):
    try:
        if not os.path.isfile(jsonFilePath):
            data = {}
            data['download'] = {
                "path":"C:/fileTransfer/download",
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

# HTTP POST방식으로 전송된 이미지를 저장
@app.route('/upload', methods=['POST'])
def save_image():
    if downloadMode.upper() == "SINGLE":
        f = request.files['file']
        fileName = f.filename.split('/')[-1]
        f.save(os.path.join(filePath, secure_filename(fileName)))
        fileSize = os.path.getsize(os.path.join(filePath, secure_filename(fileName)))
        
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} [{request.remote_addr}] >> Completed to receive the files ['{fileName}', {format(fileSize, ',')} bytes]")
        return 'done!'
    else:
        if request.method == 'POST':
            files = request.files.getlist("file")
            
            okCount = 0
            ngCount = 0
        
            with tqdm(total=len(files)) as pbar:
                for file in files:
                    try:
                        fileName = file.filename.split('/')[-1]
                        file.save(os.path.join(filePath, secure_filename(fileName)))
                        okCount += 1
                        pbar.update(1)
                    except Exception as e:
                        ngCount += 1
                        print(e)
                    
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} [{request.remote_addr}] >> Completed to receive the files [Total:{len(files)} / Succss:{okCount} / Fail:{ngCount}]")
            
            return "Success"
        
if __name__ == '__main__':
    
    printLogo()
    
    currentPath = os.path.dirname(__file__)
    jsonFilePath = os.path.join(currentPath, "config.json")
    
    CreateJsonFile(jsonFilePath=jsonFilePath)
    with open(jsonFilePath, "r") as jsonFile:
        jsonData = json.load(jsonFile)
        
        filePath = jsonData['download']['path']
        downloadMode = jsonData['download']['mode']
    
    HasFolder(filePath)
    
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} >> Download path : {filePath}")
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} >> Mode : {downloadMode}")
    
    app.run()