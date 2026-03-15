import os
import socket

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(("127.0.0.1", 9999))

dir_path = os.path.dirname(__file__)
file_path = os.path.join(dir_path, "upload")

for file_name in os.listdir(file_path):
    file = open(os.path.join(file_path, file_name), "rb")
    file_size = os.path.getsize(os.path.join(file_path, file_name))

    received_file_name = f"received_{file_name}"

    print(received_file_name)
    client.send(received_file_name.encode())
    
    client.send(str(file_size).encode())
    data = file.read()
    client.sendall(data)
    client.send(b"<END>")

    file.close()
    
client.close()