from zipfile import ZipFile
import cv2
import os
import tempfile
import shutil
import glob
def eval(file_path):

    try:

        class FileLengthError(Exception):
            def __init__(self,file,length,message="The folder has more than 2 files"):
                self.length=length
                self.message=message
                self.file=file
                super().__init__(self.message)
            
            def __str__(self) :
                return  f"{self.message} (The original file):{self.file} (The file length):{self.length}"


        def extract_zip(zip_path, extract_dir):
            with ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

        def file_check(zip_path):
            zip_fp=ZipFile(zip_path,'r')
            foldername,filename=(zip_fp.namelist()[0],zip_fp.namelist()[1:])
            file_exist=[1 if file.endswith('pdf') or file.endswith('txt') else 0 for file in filename ]
            if len(filename) > 4:
                raise Exception("The Submitted Files are more than required in Zip Archive")
            elif len(filename) < 4:
                raise Exception("Some files .. text or pdf missing in Zip Archive")
            
            if not(all(file_exist)):
                 raise Exception("Text or Pdf files are missing in Zip Archive")

            
            return foldername,filename


        def solution_score(solFile1,solFile2):   #### Evaluation Script ###
            flag1,flag2=0,0
            find_words=['1',"gaussian"]
            
            with open(solFile1, 'r') as f1, open(solFile2, 'r') as f2:
                
                first_line_f1 = f1.readline().strip()
                first_line_f2 = f2.readline().strip() 
                
                if find_words[0] in first_line_f1.lower() and find_words[1] in first_line_f1.lower():
                    flag1=1
                if find_words[0] in first_line_f2.lower() and find_words[1] in first_line_f2.lower():
                    flag2=1
            
            return flag1+flag2

        zip_path = file_path
        main_parent_path= os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        extract_dir = os.path.join(main_parent_path,"Submitted/CV_1")  # Create a temporary directory
        foldername,filenames=file_check(zip_path)
        extract_zip(zip_path, extract_dir)
       
        txt_file_path=glob.glob(os.path.join(extract_dir, foldername)+'/*.txt')
        

        solImg1_path = txt_file_path[0]
        solImg2_path = txt_file_path[1]

        score=solution_score(solImg1_path,solImg2_path)

        if score < 0:
            raise Exception(f"Your Score is low : {0} , Resubmit the Assignment")
        
        # print("Total score is: ",score*5/2)
        return {'score':(score*5)/2,'err':False}
    
    except Exception as e:

        if type(e).__name__ == "Exception":
            return {'error':str(e),'err':True}
        
        else:

         return {'error':f"{type(e).__name__}, Resubmit Assignment",'err':True}


