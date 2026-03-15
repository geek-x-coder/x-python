import os

user_input = f""
search_string = f""

with open (user_input + os.sep + "find_text.log", 'a', encoding='utf-u') as ff : 
    for (path, dir, files) in os.walk(user_input) : 
        # print(path, dir, files)
        
        for filename in files : 
            if not filename.endswith(".java") : 
                continue
            
            # print(filename)
            with open(path + os.sep + filename, 'r', encoding='utf-8') as f :
                line_no = 0
                while True : 
                    line = f.readline()
                    if not line : break
                    
                    line_no = line_no + 1
                    
                    try : 
                        if search_string in line :
                            print("=====================================================")
                            print(f"{path + os.sep + filename}({line_no}) \t -> \t {line}")
                            ff.write(f"{path + os.sep + filename}({line_no}) \t -> \t {line}")
                        else :
                            pass
                    except Exception as e:
                        print({e})
                        
                f.close()
                
    ff.close()