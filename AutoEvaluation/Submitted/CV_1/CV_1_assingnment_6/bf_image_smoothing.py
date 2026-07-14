"""
@file: bilateralFilter.py
@author: Darshan Sharma
@brief: Bilateral filter implementation from scratch
@date: 28-04-2024
@copyright: Deep Eigen Copyright (c) 2024
"""

import math
import numpy as np
import cv2

"""
Class : Bilateral Filter
Parameters:
    sigmaSpace : Standard deviation in the spatial domain
    sigmaColor : Standard deviation in the color range domain
    filterSize : Diameter of the filter
"""
class BilateralFilter:
    def __init__(self, sigmaSpace, sigmaColor, filterSize):
        self.sigma_s = float(sigmaSpace)
        self.sigma_r = float(sigmaColor)
        self.d = filterSize # Filter diameter

    def __call__(self, in_img):
        out_img = np.zeros_like(in_img)

        # Iterating through the rows and columns of the image
        for r in range(out_img.shape[0]):
            for c in range(out_img.shape[1]):
                for ch in range(out_img.shape[2]):
                    # Init Normalization factor
                    W_p = 0.0
                    filtered_intensity = 0.0

                    # Iterating through bilateral filter
                    for i in range(-(self.d-1)//2, ((self.d-1)//2)+1):
                        for j in range(-(self.d-1)//2, ((self.d-1)//2)+1):

                            # Checking whether we are accessing pixel elements within the image boundary
                            if (r+i >= 0 and r+i < out_img.shape[0]) and (c+j >= 0 and c+j < out_img.shape[1]):
                                p = [r,c]
                                q = [r+i, c+j]
                                I_p = float(in_img[r][c][ch])
                                I_q = float(in_img[r+i][c+j][ch])
                                w = self.__gaussian(self.__euclidean_dist(p,q), self.sigma_s) * self.__gaussian(abs(I_p - I_q), self.sigma_r)
                                filtered_intensity += I_q * w
                                W_p += w

                    # Normalization
                    filtered_intensity /= W_p
                    out_img[r][c][ch] = int(np.round(filtered_intensity))

        return out_img
    
    def __gaussian(self, x, sigma):
        # g = math.exp(-(x * x) / (2 * sigma * sigma)) / math.sqrt(2 * math.pi * sigma * sigma)
        g = np.exp(-(x * x) / (2 * sigma * sigma)) / (2 * np.pi * sigma * sigma)
        return g
    
    def __euclidean_dist(self, p, q): # L2 norm
        d0 = (p[0] - q[0])**2
        d1 = (p[1] - q[1])**2
        dist = math.sqrt(d0 + d1)
        return dist
