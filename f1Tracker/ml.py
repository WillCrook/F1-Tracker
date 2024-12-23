import numpy as np
import pandas as pd
from loguru import logger
import xgboost as xgb
import warnings
import requests
import zipfile
import io
from sklearn.model_selection import cross_val_score

#grab zip file containing all necessary data from the internet     
zip_file_url = "https://ergast.com/downloads/f1db_csv.zip"
logger.info(f'Getting {zip_file_url}')
r = requests.get(zip_file_url)
zip_file = zipfile.ZipFile(io.BytesIO(r.content))
dfs = {text_file.filename: pd.read_csv(zip_file.open(text_file.filename))
       for text_file in zip_file.infolist()
       if text_file.filename.endswith('.csv')}
logger.info(f'Found {dfs.keys()}')
warnings.filterwarnings('ignore')    

#sort the various csv files downloaded into their respective dataframe
df_drivers = dfs["drivers.csv"]
df_races = dfs["races.csv"]
df_results = dfs["results.csv"]
df_qualifying = dfs["qualifying.csv"]

#the next section is just building/formatting the dataframe for the machine learning model
#I have commented the various actions I am doing to the dataframe to make it clear what actions are being carried out

#add the date to df_results
df_new = df_races.loc[:, ['raceId', 'date']].drop_duplicates(subset=['raceId'])

df_new = df_new.sort_values(by='date', key=lambda x: x.str.split('-'))

df_new['raceIdOrdered'] = range(1,len(df_new)+1)

#add the correct order of races to df_results
df_results = pd.merge(df_results, df_new.loc[:, ['raceId', 'raceIdOrdered']], how='left', on=['raceId'], )


#fix the dataframe to be in the order of races
df_results = df_results.sort_values(by='raceIdOrdered')


#add the years to dataframe results
df_results = df_results.set_index('raceId').join(df_races.loc[:,['year', 'raceId']].set_index('raceId'), on='raceId').reset_index()

df_results = df_results.loc[:,['raceId', 'driverId', 'grid', 'positionOrder', 'year', 'raceIdOrdered']]

df_results = df_results.rename(columns={'positionOrder' : 'racePosition', 'grid': 'startingPosition'})

#add the year in which the different drivers started racing
min_year = df_results.groupby('driverId').min()['year']

min_year = (min_year.reset_index()).rename({'year':'yearStarted'}, axis=1)

df_results = df_results.merge(min_year, on='driverId',how='left')

#add how many races the driver has participated for  
def count_race_exp(dataframe):
    
    exp = []
    
    for index, row in dataframe.iterrows():
        
        df_new = dataframe.loc[:index]
        
        df_new = df_new[df_new['driverId'] == row['driverId']]
        
        exp.append(len(df_new))
        
    return exp

df_results['driverExpRaces'] = count_race_exp(df_results)

df_results[df_results['driverId'] == 9] 

#add the all the years to df_qualifying

years = df_races.loc[:,['year', 'raceId']].set_index('raceId')

df_qualifying = df_qualifying.set_index('raceId').join(years, on='raceId').reset_index()

#just include the qualifying and races from the hybrid era (2014 onwards)

df_qualifying = df_qualifying[(df_qualifying['year'] >= 2014)]

df_results = df_results[(df_results['year'] >= 2014)]

#remove the drivers in the table that didn't start a race 

df_results = df_results[df_results['startingPosition'] != 0]

#for some races there is missing quali data so in those races I have removed the data 
x = df_results['raceId'].unique()
y = df_qualifying['raceId'].unique()

np.where(np.isin(x, y) == False)

df_results = df_results[df_results['raceId'].isin(y)]

x = df_results['raceId'].unique()

#now we can combine the race data and quali data together into one dataframe

dataframe = pd.merge(df_results, df_qualifying,  how='left', left_on=['raceId','driverId'], right_on = ['raceId','driverId'])

dataframe = dataframe.drop(['year_y', 'constructorId', 'qualifyId', 'number'], axis = 1)

dataframe = dataframe.rename(columns={'year_x' : 'year', 'position' : 'qualiResultPosition'})

#adding the drivers nationality to the dataframe to add another data point for the machine learning model

dataframe = dataframe.merge(df_drivers.loc[:,['driverId', 'nationality']],how='left', on='driverId')

#there are instances where the nationality of the driver is unknown



#some drivers dont set a laptime in q1 
#and also they dont set laptimes if they don't advance to the next round of quali
dataframe = dataframe.replace('\\N', np.nan) #replace \\n with not a number
dataframe = dataframe[dataframe['q1'].notnull()] #only keep rows where there is data
dataframe = dataframe.fillna(0) #fill any not a number rows with 0

#need to split the lap time strings into the format [minute, sec, millisec]
def get_time_lst(dataframe, time_column):
    split_time = dataframe[time_column].str.split(pat=r':|\.').fillna(0)
    return split_time

dataframe['q1_lst'] = get_time_lst(dataframe, 'q1')
dataframe['q2_lst'] = get_time_lst(dataframe, 'q2')
dataframe['q3_lst'] = get_time_lst(dataframe, 'q3')

def convert_to_msec(time_lst):
    
    if time_lst != 0:
    
        return int(time_lst[0])*60000 + int(time_lst[1])*1000 + int(time_lst[2])
    
    return 0

dataframe['q1Msec'] = dataframe.apply(lambda x: convert_to_msec(x['q1_lst']), axis=1)
dataframe['q2Msec'] = dataframe.apply(lambda x: convert_to_msec(x['q2_lst']), axis=1)
dataframe['q3Msec'] = dataframe.apply(lambda x: convert_to_msec(x['q3_lst']), axis=1)

#added the max pace in the session as another indicator for the predicition model

dataframe['maxPace'] = dataframe.loc[:, ['q1Msec', 'q2Msec', 'q3Msec']].max(axis=1)


#adding the mean pace in session is another useful indicator for the prediction model

dataframe['meanPace'] = dataframe.loc[:, ['q1Msec', 'q2Msec', 'q3Msec']].sum(axis=1) / (dataframe.loc[:, ['q1Msec', 'q2Msec', 'q3Msec']] != 0).sum(axis=1)
dataframe = dataframe.drop(['q1_lst', 'q2_lst', 'q3_lst', 'q1', 'q2', 'q3'], axis = 1)

#adding the drivers experience in years on top of the experience in results just to include another datapoint
dataframe['driverExpYears'] = dataframe['year'] - dataframe['yearStarted']

dataframe[dataframe['driverId'] == 9]

def XGBoost_model_train(X, Y, test_size=0.2, cv=10):
    #split the dataset into training and testing sets
    #X_train, X_test, Y_train, Y_test = train_test_split(X, Y, test_size=test_size, random_state=42)

    # Initialize the XGBoost model
    model = xgb.XGBClassifier(objective="multi:softmax", num_class=len(set(Y)), random_state=42)

    #cross-validation to evaluate model performance so I can give a certaincy
    cv_scores = cross_val_score(model, X, Y, cv=cv, scoring='accuracy') #certaincy
    #log the accuracy so I can see it from the terminal 
    logger.debug("Mean Accuracy:", np.mean(cv_scores)) #so I can see improvements if I change the datapoints/model

    #fit the model on the training set
    model.fit(X, Y)
    accuracy = round(np.mean(cv_scores)*100)

    return model, accuracy

def getRacePredictions():
    #data = X, target = y
    X = dataframe[['startingPosition', 'driverExpYears', 'meanPace', 'maxPace']]  # Select features
    Y_position = dataframe["racePosition"] - 1

    #run machine learning model
    model, accuracy = XGBoost_model_train(X, Y_position)

    #create a dictionary to map driverId to the driver's code to display to the website
    df_drivers['driverCode'] = df_drivers['code'] 
    driver_id_to_code = df_drivers.set_index('driverId')['driverCode'].to_dict()

    #predict race positions
    X_test = X.tail(20)
    X_full = dataframe.tail(20)
    X_full['predict'] = model.predict(X_test) + 1  #add 1 to revert to original race positions as the indexing starts at 0

    #create a list of dictionaries for driver predictions with certainty and rank
    predictions_output = []

    for idx, row in X_full.iterrows():
        driver_id = row['driverId']  #get the driver ID from the row
        driver_code = driver_id_to_code.get(driver_id, "Unknown Driver")  #map to driver code
        predicted_position = row['predict']  #get the predicted position

        #create the dictionary for each driver
        driver_prediction = {
            'driver': driver_code,
            'rank': str(predicted_position)
        }
        
        #append to the list
        predictions_output.append(driver_prediction)

    predictions_output.sort(key=lambda driver_prediction: int(driver_prediction['rank']))

    #change order so that there isn't duplicates of pecking order
    num = 1
    for i in predictions_output:
        i['rank'] = num
        num +=1
        
    return predictions_output, accuracy

if __name__ == '__main__':
    logger.info('Starting up...')
    logger.info(getRacePredictions())
    logger.info('Shutting down...')