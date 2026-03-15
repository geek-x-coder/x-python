import os
import pyautogui
import win32gui
import telepot
import time

def screenshot(program_title="Slack | stocktrader | Myslackers"):
    if program_title:
        hwnd = win32gui.FindWindow(None, program_title)
        if hwnd:
            win32gui.SetForegroundWindow(hwnd)
            x, y, xl, yl = win32gui.GetClientRect(hwnd)
            x, y = win32gui.ClientToScreen(hwnd, (x, y))
            xl, yl = win32gui.ClientToScreen(hwnd, (xl-x, yl-y))
            image = pyautogui.screenshot(region=(x, y, xl, yl))
            return image
        else:
            bot.sendMessage(chat_id=mc, text=f"Error: Window not found. [{program_title}]")
    else:
        image = pyautogui.screenshot()
        return image

def createDirectory(directory):
    try:
        if not os.path.exists(directory):
            os.makedirs(directory)
    except OSError:
        bot.sendMessage(chat_id=mc, text=f'Error: Creating direcotry. [{directory}]')

token = 'telegram token'
mc = 'chat id'
bot = telepot.Bot(token=token)

createDirectory('img')                      # img 전용 폴더 만들기

im = screenshot()

if im:
    now = time.strftime('%Y%m%d_%H%M%S')
    path = f"img/{now}.jpg"                 # 스크린샷 저장/불러오기 할 경로 설정

    im.save(path)                           # 스크린샷 저장하기

    bot.sendPhoto(chat_id=mc, photo=open(path, 'rb'))   # 저장된 스크린샷 파일을 텔레그램으로 보내기




