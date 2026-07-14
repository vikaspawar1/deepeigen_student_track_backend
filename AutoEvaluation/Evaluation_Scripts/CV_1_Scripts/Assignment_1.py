from zipfile import ZipFile
import cv2
import os
import tempfile
import shutil
import glob
import sys
import io
import traceback





def eval(file_path):

    
    try:

        def find_ground_truth_path():

            parent_path=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

            folders_to_check={
                "ground_truth":"Ground_Truth",
                "cv_1":"CV_1",
                "assignment_1_gt":'Assignment_1_GT'
            }

            files_to_check={
                "row_col_txt":'GTsub_row_col.txt',
                "gt_img":'groundTruth.jpg'
            }
            for root,folders,files in os.walk(parent_path):
            
            # print(folders,files)
            
                for folder in folders:
                        if folder == folders_to_check["ground_truth"]:

                            cal_path=os.path.join(parent_path,folder)
                            if os.path.exists(cal_path):
                                ground_truth_path=cal_path
                        
                        elif folder==folders_to_check["cv_1"]:
                            cal_path=os.path.join(ground_truth_path,folder)

                            if os.path.exists(cal_path):
                                ground_truth_path=cal_path
                        
                        elif folder == folders_to_check["assignment_1_gt"]:
                            cal_path=os.path.join(ground_truth_path,folder)

                            if os.path.exists(cal_path):
                                ground_truth_path=cal_path
                    
                for file in files:
                    if file == files_to_check["row_col_txt"]:
                        row_col_path=os.path.join(ground_truth_path,file)
                    
                    if file== files_to_check["gt_img"]:
                        img_path=os.path.join(ground_truth_path,file)

            
        
            return img_path,row_col_path
        
        class UnequalDimensionsError(Exception):
            """Exception raised for errors in the input dimensions.

            Attributes:
                shape1 -- input image shape which caused the error
                shape2 -- input image shape which caused the error
                message -- explanation of the error
            """

            def __init__(self, shape1, shape2, message="Dimensions of the image are not equal"):
                self.shape1 = shape1
                self.shape2 =shape2
                self.message = message
                super().__init__(self.message)

            def __str__(self):
                return f'{self.message} (Sol_img_shape: {self.shape1}, GroundTruth_Image: {self.shape2})'

        def extract_zip(zip_path, extract_dir):
            with ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

        def file_check(zip_path):
            zip_fp=ZipFile(zip_path,'r')
            foldername,filename=(zip_fp.namelist()[0],zip_fp.namelist()[1:])
            file_exist=[1 if file.endswith('jpg') or file.endswith('txt') else 0 for file in filename ]
            if len(filename) > 2:
                raise Exception("The Submitted Files are more than required in Zip Archive")
            elif len(filename) < 2:
                raise Exception("Some files .. text or Img missing in Zip Archive")
            
            if not(all(file_exist)):
                 raise Exception("Text or Img files are missing in Zip Archive")

            
            return foldername,filename


        def solution_score(solFile,gTfile,solImg,groundTruth):   #### Evaluation script ####
            
            size1 = os.path.getsize(solFile)
            size2 = os.path.getsize(gTfile)

           
            if(solImg.shape != groundTruth.shape):
                print("Incorrect Dimension..")
                raise  UnequalDimensionsError(solImg.shape,groundTruth.shape)
                
                

            if size1 != size2:
                print("Error: File sizes are not the same.")
                
            
            no_match=0
            wrong_count=0
            count=0
            with open(solFile, 'r') as f1, open(gTfile, 'r') as f2:
                for line1, line2 in zip(f1, f2):
                    
                    x1, y1 = map(int, line1.strip().split(','))
                    x2, y2 = map(int, line2.strip().split(','))
                    
                    if any(solImg[x1, y1, :] != groundTruth[x1, y1, :]):
                        no_match += 1

                    
                    if (x1, y1) != (x2, y2):
                        wrong_count+=1
                    count+=1
            # print("the incorrect pixels in image for given coordinates are: ", no_match)
            return (wrong_count/count,no_match/count)


        main_parent_path= os.path.dirname(os.path.dirname(os.path.dirname(__file__)))   ### get the  assignment eval path
        
        zip_path = file_path

        foldername,filenames=file_check(zip_path)
        
        extract_dir = os.path.join(main_parent_path,"Submitted/CV_1")  # Create a temporary directory
       
        extract_zip(zip_path, extract_dir)
        
        img_file_path=glob.glob(os.path.join(extract_dir,foldername)+'/*.jpg')
        
        txt_file_path=glob.glob(os.path.join(extract_dir, foldername+'/*.txt'))

        print('img_file-- ',img_file_path,txt_file_path)
        
        solImg_path = img_file_path[0]
        
        solFile_path = txt_file_path[0]

        groundTruth_path,GTsolFile_path=find_ground_truth_path()
        
        solImg = cv2.imread(solImg_path)
        
        groundTruth = cv2.imread(groundTruth_path)
     
        file_score,img_score = solution_score(solFile_path, GTsolFile_path, solImg,groundTruth)

        
        f_score=round((1-file_score)*2.5+(1-img_score)*2.5,3)

        if f_score < 1.0 :
            
            raise Exception(f" Your Score is low: {0} , Resubmit the Assignment ")

        return {'score':f_score,"err":False}
    
    except Exception as e:
        if type(e).__name__=='IndexError':
            return {"error":"Index error : Resubmit the  correct Assignment", "err":True}
        
        elif type(e).__name__ == "UnequalDimensionsError":
             return {"error":"Dimensionerror : Resubmit the  assignment with correct Image dimension", "err":True}
        
        elif type(e).__name__ == "Exception":
            return {"error":str(e),"err":True}
       
        else:
          return {"error":f"{type(e).__name__}, Resubmit the Asssignment","err":True}

