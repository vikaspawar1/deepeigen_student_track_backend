import sys
import json
import cv2
from bf_image_smoothing import BilateralFilter

n = len(sys.argv)
if n < 2:
    raise Exception("Enter params.json file path.")

json_file_path = sys.argv[1]

# Read params json file
json_fp = open(json_file_path)
params = json.load(json_fp)

if params["filter_size"] < 3 or params["filter_size"] % 2 == 0:
    raise Exception("Please select filter size >= 3 and it should be an ODD number.")

# Create BilateralFilter object
bilateralFilter = BilateralFilter(params["std_spatial"],
                     params["std_color"],
                     params["filter_size"])

# Read input
inputImg = cv2.imread(params["input"])

# Perform bilateralFiltering on input image
bf_output = bilateralFilter(inputImg)

# Calling opencv bilaterfilter function
cvBF_output = cv2.bilateralFilter(inputImg,
                                  params["filter_size"],
                                  params["std_spatial"],
                                  params["std_color"]
                                  )

cv2.imwrite("output.jpg", bf_output)
cv2.imwrite("output_cv.jpg", cvBF_output)