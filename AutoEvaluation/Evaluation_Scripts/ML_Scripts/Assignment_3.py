from ML_Scripts.assign_3_main  import predict
import pandas as pd
import numpy as np
from zipfile import ZipFile
import os
import tempfile
import shutil
import random
import re




# def cleanup_temp_directory(directory):
#     shutil.rmtree(directory)

def eval(path):
    try:
        def extract_zip(zip_path, extract_dir):
          with ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
            zip_ref.close()
        
        def file_check(zip_path):
            zip_fp=ZipFile(zip_path,'r')
            foldername,filename=(zip_fp.namelist()[0],zip_fp.namelist()[1:])
            file_exist=[1 if  file.endswith('txt') or file.endswith('pdf')  else 0 for file in filename ]
            zip_fp.close()
            if len(filename) > 3:
                raise Exception("The Submitted Files are more than required in Zip Archive")
            elif len(filename) < 3:
                raise Exception("Some text or Pdf files missing in Zip Archive")
            
            if not(all(file_exist)):
                 raise Exception("Text files or Pdf files are missing in Zip Archive")

            
            return foldername,filename

            
        zip_file_path = path
        current_dir_path=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        submitted_dir_path=os.path.join(current_dir_path,"Submitted")
        extract_dir_path=os.path.join(submitted_dir_path,"ML")
        foldername,filenames=file_check(zip_file_path)
        extract_zip(zip_file_path,extract_dir_path)
        actual_file=[filename for filename in filenames if filename.endswith('txt')][0]
        
        
        #### Evaluation script ######
        
        
        data_string=[]
        with open(os.path.join(extract_dir_path,actual_file)) as file1:
            lines=file1.readlines()
            for line in lines:
                line = line.strip("\n")
                data_string.append(line)
       
        w_arr = np.array([float(i) for i in data_string[0].split(',')])
        print("w arr : ",w_arr)
        bias = float(data_string[1])
        learning_rate = float(data_string[2])
        w_arr_new=np.insert(w_arr, 0, bias)
        ground_truth_path=os.path.join(current_dir_path,"Ground_Truth","ML","Assignment_3_GT","lap_data_reg.txt")
        data = pd.read_csv(ground_truth_path, header=None)
        x = data[0]
        y = data[1]
        pred = predict(x, w_arr_new)
        residuals = y - pred
        SSR = np.sum(residuals**2)
        mean_actual = np.mean(y)
        SST = np.sum((y - mean_actual)**2)
        R_squared = 1 - (SSR / SST)
        accuracy=0
        
        if -200 >= R_squared <= -100 or 100 >= R_squared <= 200:
            accuracy = 90
            print(accuracy)
        elif -300 >= R_squared <= -200 or 200 >= R_squared <= 300:
            accuracy = 80
            print(accuracy)
        elif -400 >= R_squared <= - 300 or 300 >= R_squared <= 400:
            accuracy = 70
            print(accuracy)
        elif -500 >= R_squared <= -400 or 400 >= R_squared <= 500:
            accuracy = 60
            print(accuracy)
        elif -600 >= R_squared <= -500 or 500 >= R_squared <= 600:
            accuracy = 50
            print(accuracy)
        elif R_squared <= -600 or 600 >= R_squared:
            accuracy = 40
            print(accuracy)
        elif -100 <= R_squared <= 100:
            accuracy = 100
            
        else:
            accuracy = 20
            raise Exception(f"Your evaluation score is low {0.0},  Resubmit Assignement")
        
        ### end ##
        
        print("score : ",accuracy)       
        return {'score':((accuracy)/100)*5,'err':False}
    
       
    
    except Exception as e:
        if type(e).__name__ == "Exception":
            return{'error':str(e), "err":True}
        else:
          return {'error':f"{type(e).__name__}, Resubmit Assignment","err":True}

