import os
import time

target_path = r""

def replace_in_file(file_path, old_str, new_str) : 
    # 파일 읽어들이기
    with open(file_path, 'rt', encoding='utf-8') as fr :
        read_file = fr.read()
        
    # old_str -> new_str 치환
    with open(file_path, 'wt', encoding='utf-8') as fw :
        fw.write(read_file.replace(old_str, new_str))
        
for (root, directories, files) in os.walk(target_path) :
    for file in files :
        try :
            if file.endswith('sql') :
                replace_in_file(os.path.join(target_path, file), 'old_str', 'new_str')
                print(f"O[{time.strftime('%Y-%m-%d %H:%M:%S')}] >> success to replace text [{file}]")
        
        except Exception as e :
            print(f"X[{time.strftime('%Y-%m-%d %H:%M:%S')}] >> failed to replace text [{file}]")