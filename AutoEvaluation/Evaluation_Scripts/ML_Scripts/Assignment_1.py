from AutoEvaluation.Evaluation_Scripts.ML_Scripts.assign_1_main import predict,norm_predict

import pandas as pd
import numpy as np
import zipfile

import random
import os
import re


def eval(path):

    try:

        def without_normalization(learning_param_file1):      #### Evaluation Scripts #####
            data_string=[]
            with open(learning_param_file1) as file1:
                lines=file1.readlines()
                for line in lines:
                    line = line.strip("\n")
                    data_string.append(line)
    
            w_arr = np.array([float(i) for i in data_string[0].split(',')])
            bias = float(data_string[1])
            learning_rate = float(data_string[2])
            w_arr_new=np.insert(w_arr, 0, bias)
            current_dir_path=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            ground_truth_file_path=os.path.join(current_dir_path,"Ground_Truth","ML","Assignment_1_GT","data_regress.txt")
            data = pd.read_csv(ground_truth_file_path, header=None)
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
                accuracy = 0
            
            return accuracy
        
        def with_normalization(learning_param_file2):       #### Evaluation Scripts #####
            data_string2=[]
            with open(learning_param_file2) as file2:
                lines=file2.readlines()
                for line in lines:
                    line = line.strip("\n")
                    data_string2.append(line)
    
            w_arr2 = np.array([float(i) for i in data_string2[0].split(',')])
            bias2 = float(data_string2[1])
            learning_rate2 = float(data_string2[2])
            current_dir_path=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            ground_truth_file_path=os.path.join(current_dir_path,"Ground_Truth","ML","Assignment_1_GT","data_regress.txt")
            data = pd.read_csv(ground_truth_file_path, header=None)
            x = data[0]
            y = data[1]
            w_arr_new2=np.insert(w_arr2, 0, bias2)
            norm_pred = norm_predict(x, w_arr_new2)
            residuals = y - norm_pred
            SSR = np.sum(residuals**2)
            mean_actual = np.mean(y)
            SST = np.sum((y - mean_actual)**2)
            R_squared2 = 1 - (SSR / SST)
            accuracy=0
            
            if -200 >= R_squared2 <= -100 or 100 >= R_squared2 <= 200:
                accuracy= 90
                
            elif -300 >= R_squared2 <= -200 or 200 >= R_squared2 <= 300:
                accuracy = 80
                
            elif -400 >= R_squared2 <= - 300 or 300 >= R_squared2 <= 400:
                accuracy = 70
                
            elif -500 >= R_squared2 <= -400 or 400 >= R_squared2 <= 500:
                accuracy = 60
                
            elif -600 >= R_squared2 <= -500 or 500 >= R_squared2 <= 600:
                accuracy = 50
            elif R_squared2 <= -600 or 600 >= R_squared2:
                accuracy = 40
            elif -100 <= R_squared2 <= 100:
                accuracy = 100
                
            else:
                accuracy = 0
            
            return accuracy

        def file_check(zip_path):
            zip_fp=zipfile.ZipFile(zip_path,'r')
            foldername,filename=(zip_fp.namelist()[0],zip_fp.namelist()[1:])
            file_exist=[1 if  file.endswith('txt') or file.endswith('py') else 0 for file in filename ]
            zip_fp.close()
            if len(filename) > 4:
                raise Exception("The Submitted Files are more than required in Zip Archive")
            elif len(filename) < 4:
                raise Exception("Some files .. text or python missing in Zip Archive")
            
            if not(all(file_exist)):
                 raise Exception("Text or python files are missing in Zip Archive")

            
            return foldername,filename

        def extract_zip(zip_path,extract_dir):
            zip_fp=zipfile.ZipFile(zip_path,'r')
            zip_fp.extractall(extract_dir)
            zip_fp.close()
        
        
        file_path = path
        current_dir_path=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        submitted_dir_path=os.path.join(current_dir_path,"Submitted") 
        extract_dir_path=os.path.join(submitted_dir_path,"ML")
        foldername,filenames=file_check(file_path)
        extract_zip(file_path,extract_dir_path) 
        actual_file_paths=["learningParam_1","learningparam_1","learningParam_2","learningparam_2"]
        # print("actual file paths : ",filenames)
        file_1=[filename for filename in filenames if actual_file_paths[0] in filename or actual_file_paths[1] in filename][0]
        # print('file 1',file_1)
        file_2=[filename for filename in filenames if actual_file_paths[2] in filename or actual_file_paths[3] in filename][0]
        # print("file 2",file_2)
        learning_param1_filepath=os.path.join(extract_dir_path,file_1) 
        learning_param2_filepath=os.path.join(extract_dir_path,file_2)

        print(learning_param1_filepath,learning_param2_filepath)
        
        accuracy1=without_normalization(learning_param1_filepath)
        accuracy2=with_normalization(learning_param2_filepath)
         
        if accuracy2+accuracy1 < 40 :

            raise Exception("Your score is low , Resubmit the Assignment")
        
        print("total acc :",accuracy2+accuracy1)

        return {'score':round((accuracy1+accuracy2)/200)*5,'err':False}

    except Exception as e:
        if type(e).__name__ == "Exception":
             return {'error':str(e),'err':True}
        else:
         return {'error':f"{type(e).__str__(e)}, Resubmit the assignment",'err':True}