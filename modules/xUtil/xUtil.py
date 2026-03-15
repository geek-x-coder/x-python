import os

def printLogo(application) : 
    # os.system("cls")
    logo = f"""\033[95m
        
        ,--.   ,--.      ,--.                             
        |  |   |  |,---. |  |,---. ,---. ,--,--,--.,---.  
        |  |.'.|  | .-. :|  | .--'| .-. ||        | .-. : 
        |   ,'.   \   --.|  \ `--.' '-' '|  |  |  \   --. 
        '--'   '--'`----'`--'`---' `---' `--`--`--'`----' 
                                                        
        {application.title} {application.version}
        Powered by X (geek-x-coder)
        
        \033[0m"""
    print(logo)
    
def hasDirectory(directory):
    try :
        if not os.path.exists(directory):
            os.makedirs(directory)
    except OSError:
        print(f"Error: Creating directory. {directory}", "exception");