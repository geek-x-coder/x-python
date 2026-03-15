import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from modules.xConfiguration.xConfiguration import Configuration
import modules.xUtil.xUtil as util


class Application:
    def __init__(self, title, version):
        self.title = title
        self.version = version


configFilePath = os.path.join(os.path.dirname(__file__), "config.json")

print(configFilePath)

config = Configuration(configFilePath).load()

appConfig = Application(config["application"]["title"], config["application"]["version"])

util.printLogo(appConfig);

print("hello world")