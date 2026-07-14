import zipfile
import os
import sys
def eval(zip_path):
    try:
        # Define the fixed file names to check

        def file_check(zip_path):
            zip_fp=zipfile.ZipFile(zip_path,'r')
            foldername,filename=(zip_fp.namelist()[0],zip_fp.namelist()[1:])
            file_exist=[1 if  file.endswith('txt')  else 0 for file in filename ]
            zip_fp.close()
            if len(filename) > 6:
                raise Exception("The Submitted Files are more than required in Zip Archive")
            elif len(filename) < 6:
                raise Exception("Some text missing in Zip Archive")
            
            if not(all(file_exist)):
                 raise Exception("Text files are missing in Zip Archive")

            
            return foldername,filename
         
        def extract_zip(zip_path,extract_dir):
            zip_fp=zipfile.ZipFile(zip_path,'r')
            zip_fp.extractall(extract_dir)
            zip_fp.close()
        

        current_dir_path=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        submitted_dir_path=os.path.join(current_dir_path,"Submitted")
        extraction_path = os.path.join(submitted_dir_path, "ML")
        print(f"Extraction path: {extraction_path}")
        foldername,filenames=file_check(zip_path)
        extract_zip(zip_path,extraction_path)
        
        actualfiles,expected_files = ([filename for filename in filenames if "errors" not in filename],[os.path.basename(filename) for filename in filenames if "errors" not in filename])
        print("expected :",expected_files)
        correct_values={}
        for file in expected_files:
            if file.startswith("P1_") or file.startswith("p1_"):
                correct_values[file] = [("9", None)]
            elif file.startswith("P2_") or file.startswith('p2_'):
                correct_values[file]= [("5", None)]
            elif file.startswith('P3_') or file.startswith('p3_'):
                correct_values[file]= [("5", None, None)]

        
        # print('correct values :',correct_values)
        #### Evlaution Script ####
        score = 0
        total_checks = 0

        for file_name in actualfiles:
            file_path = os.path.join(extraction_path, file_name)
          
            with open(file_path, 'r') as file:
                lines = file.readlines()
            
            for i, line in enumerate(lines):
                try:
                    if i < len(correct_values[os.path.basename(file_name)]):
                        expected = correct_values[os.path.basename(file_name)][i]
                        values = line.strip().split(',')

                        if all(e is None or (j < len(values) and e == values[j]) for j, e in enumerate(expected)):
                            score += 1
                        total_checks += 1
                except KeyError:
                    print("key error")

        # Calculate the final score out of 100
        final_score = (score / total_checks) * 5 if total_checks else 0

        #### Script end ########

        if final_score <1.0:
            raise Exception(f"Your evaluation score is low {0.0},  Resubmit Assignement")
        
        print("final_score :",final_score)

        return {"score": final_score, "err": False}

    except Exception as e:
        if type(e).__name__ == "Exception":
            return {"error": str(e), "err": True}
        else:
         return {"error": type(e).__name__, "err": True}







# import pandas as pd
# import numpy as np
# import zipfile
# import os
# def eval(path):
#     try:
#         file_path =path
#         current_dir_path=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
#         submitted_dir_path=os.path.join(current_dir_path,"Submitted","ML") 
#         error_msg="FILE LENGTH ERROR :The minimum files should be 4"
#         with zipfile.ZipFile(file_path, 'r') as zip_ref:
#             zip_ref.extractall(submitted_dir_path)
#             file_name = zip_ref.namelist()[0]
#             if len(file_name)>6:
#                 raise Exception(error_msg)
           
#             print(zip_ref.namelist())
#             data_string = []
#             with open(os.path.join(submitted_dir_path,file_name)) as file1,open() :
#                 lines = file1.readlines()
#                 for line in lines:
#                     line = line.strip("\n")
#                     data_string.append(line)

#         P1 = data_string[3].split(',') 
#         P2 = data_string[4].split(",")
#         P3 = data_string[5].split(",")

#         print(P1,P2,P3)

#         def check(P1, P2, P3):
#             score = []
#             flag = 0
#             for i, val in enumerate(P1):
#                 if i > 0 and int(val) == 5:
#                     flag += 1
#                     # print(val)
#                     score.append(int(val))

#             for i, val in enumerate(P2):
#                 if i > 3 and int(val) == 8:
#                     flag += 1
#                     # print(val)
#                     score.append(int(val))

#             for i, val in enumerate(P3):
#                 if i > 3 and int(val) == 7:
#                     flag += 1
#                     # print(val)
#                     score.append(int(val))

#             # print(score)
#             key1 = ["P1", "P2", "P3"]
#             src = dict(zip(key1,score))
#             # print(src)
            
#             for key, val in dict.items(src):
#                 if val == 0:
#                     print(f"In the given assignment {key} is wrong")
#                     continue
#                 elif val != 0:
#                     print(f"The given assignment {key} is correct")
#             return flag*33.3

#         val=check(P1, P2, P3)
#         return {"score":(val/100)*5,"err":False}
#     except Exception as e:
#         return {"error":type(e).__str__(e),"err":True}