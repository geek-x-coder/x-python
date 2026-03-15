import requests

class Messenger:
    def __init__(self, type, token, channel) :
        self.type = type
        self.token = token
        self.channel = channel

    def _post_message(self, token, channel, text):
        response = requests.post("https://slack.com/api/chat.postMessage",
                                headers={"Authorization": "Bearer " + token},
                                data={"channel": channel, "text": text}
                                )

    def send(self, text) : 
        self._post_message(self.token, self.channel, text)

if __name__ == "__main__":
    msg = Messenger(type='slack', token='', channel='')
    
    msg.send('test123')
    
