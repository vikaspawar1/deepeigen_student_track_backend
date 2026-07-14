import numpy as np
import pandas as pd
import os
# import matplotlib.pyplot as plt
current_dir_path=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
ground_truth_path=os.path.join(current_dir_path,"Ground_Truth","ML","Assignment_3_GT","lap_data_reg.txt")
data = pd.read_csv(ground_truth_path, header=None)
x = data[0]
y = data[1]
phi = np.column_stack((np.ones_like(x),x, x**2, x**3, x**4))
weights = np.zeros(phi.shape[1])
lr= .0000001
ep = 1000


def losses_1(y, y_pred, phi, w):
    loss_1 = np.mean(np.square(y_pred - np.dot(phi, w)))
    return loss_1

def subdifferential_l1_loss(y_true, y_pred):
    diff = y_pred - y_true
    subgrad = np.where(diff > 0, 1, np.where(diff < 0, -1, 0))
    return subgrad

def gradient_descent(phi,y,lr,ep,w):
    losses=[]
    for i in range(ep):
        prediction=np.dot(phi,w)
        #print(phi)
        subgrad=subdifferential_l1_loss(y,prediction)
        gradient=np.dot(phi.T,subgrad)
        
        w-=lr*gradient
        y_pred=np.dot(phi,weights)
        l=losses_1(y,y_pred,phi,w)
        losses.append(l)
        #print(f'iterations {i + 1}, weight: {w}, losses: {l}')
    return w,losses
           
def predict(x, w):
    phi = np.column_stack((np.ones_like(x),x, x**2, x**3,x**4))
    y_predict = np.dot(phi, w)
    return y_predict
    
# weights,losses=gradient_descent(phi,y,lr,ep,weights)
# print(weights)
# y_pred = predict(x, weights)


# plt.figure(figsize=(8, 6))
# plt.scatter(x, y, c="r", label="Actual Data")
# plt.scatter(x, y_pred, c="b", label="Predicted Data")
# plt.legend()
# plt.show()