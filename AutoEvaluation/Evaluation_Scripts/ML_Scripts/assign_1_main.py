import numpy as np
import pandas as pd
import os
current_dir_path=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
ground_truth_file_path=os.path.join(current_dir_path,"Ground_Truth","ML","Assignment_1_GT","data_regress.txt")
data = pd.read_csv(ground_truth_file_path, header=None)
x = data[0]
y = data[1]
phi = np.column_stack((np.ones_like(x),x, x**2, 0.5*x**3))
weights = np.zeros(phi.shape[1])
lr= .0000001
ep = 1000


def losses_1(y, y_pred, phi, w):
    loss_1 = np.mean(np.square(y_pred - np.dot(phi, w)))
    return loss_1

def normalize_data(phi):
    first_column = phi[:, 0:1]
    rest_of_columns = phi[:, 1:]
    mean_values = np.mean(rest_of_columns, axis=0)
    std_dev_values = np.std(rest_of_columns, axis=0)
    rest_of_columns_normalized=(rest_of_columns-mean_values)/std_dev_values
    phi_hat = np.concatenate([first_column, rest_of_columns_normalized], axis=1)
    return phi_hat

def gradient_descent(phi,y,lr,ep,w):
    losses=[]
    for i in range(ep):
        prediction=np.dot(phi,w)
        #print(phi)
        gradient=np.dot(phi.T,prediction-y)
        
        w-=lr*gradient
        y_pred=np.dot(phi,weights)
        l=losses_1(y,y_pred,phi,w)
        losses.append(l)
        #print(f'iterations {i + 1}, weight: {w}, losses: {l}')
    return w,losses
           
def predict(x, w):
    phi = np.column_stack((np.ones_like(x),x, x**2, 0.5*x**3))
    y_predict = np.dot(phi, w)
    return y_predict

def norm_predict(x, w):
    phi = np.column_stack((np.ones_like(x),x, x**2, 0.5*x**3))
    phi_hat= normalize_data(phi)
    y_predict = np.dot(phi_hat, w)
    return y_predict

# phi_hat=normalize_data(phi)
      
# weights,losses=gradient_descent(phi,y,lr,ep,weights)
# y_pred = predict(x, weights)


# plt.figure(figsize=(8, 6))
# plt.scatter(x, y, c="r", label="Actual Data")
# plt.scatter(x, y_pred, c="b", label="Predicted Data")
# plt.legend()
# plt.show()