from zipfile import ZipFile
import zipfile
import cv2
import os
import numpy as np
import sys
def eval(file_path):
    try:
        def score_HE(npy_data):     ##### Evaluation Script #######
            ideal=129.71
            pixel_values =npy_data
            histogram, bins = np.histogram(pixel_values, bins=256, range=(0, 255))
            cdf = np.cumsum(histogram)
            cdf_normalized = cdf / float(np.sum(histogram))
            sol =  np.sum(np.abs(cdf_normalized)) 
            
            score = sol/ideal
            if score <0.8:
                score =0
            return score
        
        def score_AHE(npy_data):     ##### Evaluation Script #######
            ideal=122.49
            pixel_values =npy_data
            histogram, bins = np.histogram(pixel_values, bins=256, range=(0, 255))
            cdf = np.cumsum(histogram)
            cdf_normalized = cdf / float(np.sum(histogram))
            sol =  np.sum(np.abs(cdf_normalized)) 
            
            score = sol/ideal
            if score <0.8:
                score =0
            return score
        
        def score_CLAHE(npy_data):     ##### Evaluation Script #######
            ideal=174.9
            pixel_values =npy_data
            histogram, bins = np.histogram(pixel_values, bins=256, range=(0, 255))
            cdf = np.cumsum(histogram)
            cdf_normalized = cdf / float(np.sum(histogram))
            sol =  np.sum(np.abs(cdf_normalized)) 
            
            score = sol/ideal
            if score <0.8:
                score =0
            return score

        def file_check(zip_path):
            zip_fp=ZipFile(zip_path,'r')
            foldername,filename=([folder for folder in zip_fp.namelist() if os.path.splitext(folder)[1]==""],[filename for filename in zip_fp.namelist() if os.path.splitext(filename)[1]!=""])
            print("folders : ",foldername,filename)
            
            file_exist=[1 if file.endswith('jpg') or file.endswith('txt') or file.endswith('py') or file.endswith('npy') else 0 for file in filename ]
            if len(filename) > 9:
                raise Exception("The Submitted Files are more than required in Zip Archive")
            elif len(filename) < 9:
                raise Exception("Some files .. text or Img or Py or npy missing in Zip Archive")
            
            if not(all(file_exist)):
                 raise Exception("Text or Img or py or npy files are missing in Zip Archive")

            
            return foldername,filename  

        def extract_zip(zip_path, extract_dir):
            with ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)  
            
        zip_path = file_path

        main_parent_path= os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        extract_dir = os.path.join(main_parent_path,"Submitted/CV_1")
        foldername,filenames=file_check(zip_path)
        extract_zip(zip_path,extract_dir)   
        actual_filenames={
            "1st":'he_arr.npy',
            "2nd": 'ahe_arr.npy',
            "3rd":"clahe_arr.npy"
        }
        
        score =0 
        for file_name in filenames:
            
            if actual_filenames["1st"] in file_name:
                npy_data = np.load(os.path.join(extract_dir,file_name))
                score+=score_HE(npy_data)
            elif actual_filenames['2nd'] in file_name:
                npy_data = np.load(os.path.join(extract_dir,file_name))
                score+=score_AHE(npy_data)
            elif actual_filenames['3rd'] in file_name:
                npy_data = np.load(os.path.join(extract_dir,file_name))
                score+=score_CLAHE(npy_data)
        
        # print("score :",score) 

        if score < 1.5:
            raise Exception(f"The Score is low {score} , Resubmit Assignment")
                
        return {"score":(score/3)*5,"err":False}
        
    except Exception as e:
     if type(e).__name__ == "Exception":
         return {"error":str(e),'err':True}
     else:
        return{"error":f"{type(e).__str__(e)}, Resubmit Assignment","err":True}
            


# path='username.zip'
# eval(path)

    

