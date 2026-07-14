import os
import subprocess
import sys
from zipfile import ZipFile
import numpy as np
import cv2

def eval(file_path):
    try:

        def file_check(zip_path):
            error_msg = "You forgot to pass assignment zipfile path or image groundtruth.."
            
            file_names_list=('jpg','py','json')

            zip_fp = ZipFile(file_path, 'r')
            file_list=zip_fp.namelist()
            output_folder=file_list[0]
            zip_fp.close()
            for filename in file_list[1:]:
                if filename.endswith(file_names_list):
                    print("all files exist")
                else:
                    raise Exception(error_msg)
            return output_folder,file_list[1:]
        
        def extract_zip(zip_path, extract_dir):
            with ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)  
              
        zipfilePath = file_path
    
        main_parent_path= os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        extract_dir = os.path.join(main_parent_path,"Submitted/CV_1")
        folder,filenames=file_check(zipfilePath)
        
        extract_zip(zipfilePath,extract_dir)
        imgfile_path=[file for file in filenames if file.endswith('jpg')][0]
    
        # Calculate MSE of the student's output with groundtruth
        # Student output
         #### Evlaution Script ###########
        
        std_output = cv2.imread(os.path.join(extract_dir,imgfile_path))
        if std_output is None:
            raise Exception("FILE NOT FOUND. TEST CASE FAILED")
        
        ground_truth_img=os.path.join(main_parent_path,"Ground_Truth","CV_1","Assignment_6_GT")
        # Deep Eigen groundtruth
        deepEigen_gt = cv2.imread(f"{ground_truth_img}/BF_GT_F7_C50_S1000.jpg")
        mse = np.square(np.subtract(std_output, deepEigen_gt)).mean()


        ### Script end ########
        
        print(mse)
        if mse < 1.0:
            # print("RESULT: TEST CASE PASSED")
            return {"score":5.0,"err":False}
        else:   
            # print("RESULT: TEST CASE FAILED")
            raise Exception(f"Your evaluation score is low ,  Resubmit assignment")
    
    except Exception as e:
        if type(e).__name__ == "Exception":
            return {'error':str(e),  'err':True}
        
        else:
          return {"error":f"{type(e).__name__}, Resubmit Assignment","err":True}
    

