import numpy as np
import pandas as pd
from matplotlib import pyplot
import xgboost as xgb
from loguru import logger
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, classification_report
import warnings
import requests, zipfile, io

#Grab zip file containing all necessary data from the internet     
zip_file_url = "https://ergast.com/downloads/f1db_csv.zip"
logger.info(f'Getting {zip_file_url}')
r = requests.get(zip_file_url)
zip_file = zipfile.ZipFile(io.BytesIO(r.content))
dfs = {text_file.filename: pd.read_csv(zip_file.open(text_file.filename))
       for text_file in zip_file.infolist()
       if text_file.filename.endswith('.csv')}
logger.info(f'Found {dfs.keys()}')
warnings.filterwarnings('ignore')    

#Sort the various csv files downloaded into their respective dataframe

df_drivers = dfs["drivers.csv"]
df_races = dfs["races.csv"]
df_results = dfs["results.csv"]
df_qualifying = dfs["qualifying.csv"]

#The next section is just building/formatting the dataframe for the machine learning model
#I have commented the various actions I am doing to the dataframe to make it clear what data is being used

#Add the date to df_results

df_new = df_races.loc[:, ['raceId', 'date']].drop_duplicates(subset=['raceId'])

df_new = df_new.sort_values(by='date', key=lambda x: x.str.split('-'))

df_new['raceIdOrdered'] = range(1,len(df_new)+1)

#Add the correct order of races to df_results

df_results = pd.merge(df_results, df_new.loc[:, ['raceId', 'raceIdOrdered']], how='left', on=['raceId'], )


#Fix the dataframe to be in the order of races

df_results = df_results.sort_values(by='raceIdOrdered')


#Add the years to dataframe results

df_results = df_results.set_index('raceId').join(df_races.loc[:,['year', 'raceId']].set_index('raceId'), on='raceId').reset_index()

df_results = df_results.loc[:,['raceId', 'driverId', 'grid', 'positionOrder', 'year', 'raceIdOrdered']]

df_results = df_results.rename(columns={'positionOrder' : 'racePosition', 'grid': 'startingPosition'})

df_results.head(10)

#Add the year in which the different drivers started racing

min_year = df_results.groupby('driverId').min()['year']

min_year = (min_year.reset_index()).rename({'year':'yearStarted'}, axis=1)

df_results = df_results.merge(min_year, on='driverId',how='left')

df_results

#Add how many races the driver has participated for  

def count_race_exp(df):
    
    sol = []
    
    for index, row in df.iterrows():
        
        df_new = df.loc[:index]
        
        df_new = df_new[df_new['driverId'] == row['driverId']]
        
        sol.append(len(df_new))
        
    return sol


df_results['driverExpRaces'] = count_race_exp(df_results)

df_results[df_results['driverId'] == 9] 

#In Formula 1 the number of races raced in each year changes. 
#EVAL: How the number of races changed throught the years?

races_per_years = df_races['year'].value_counts()

race_ids_per_years = df_races.groupby('year')['raceId'].agg(list)

races_per_years = pd.concat([races_per_years, race_ids_per_years], axis=1).reset_index()

races_per_years.columns = ['Year', 'Total', 'RaceIds']

races_per_years = races_per_years.sort_values(by='Year')

races_per_years.plot(x='Year', 
           y='Total',
           kind='bar',
          xlabel = 'Year',
          ylabel = 'Total number of races',
          legend = False,
          title = 'Number of races per year')

#EVAL: Not every race for a year in data

data_for_races = df_results.loc[:,['raceId','year']].groupby('year').nunique()

data_expected = races_per_years.set_index('Year')['Total']

data_for_races = data_for_races.join(data_expected)

data_for_races['diff'] = data_for_races['Total'] - data_for_races['raceId']

data_for_races[data_for_races['diff'] != 0]

#Add the all the years to df_qualifying

years = df_races.loc[:,['year', 'raceId']].set_index('raceId')

df_qualifying = df_qualifying.set_index('raceId').join(years, on='raceId').reset_index()

#Just include the qualifying and races from the hybrid era (2014 onwards)

df_qualifying = df_qualifying[(df_qualifying['year'] >= 2014)]

df_results = df_results[(df_results['year'] >= 2014)]

#Remove the drivers in the table that didn't start a race 

df_results = df_results[df_results['startingPosition'] != 0]

#For some races there is missing quali data so in those races I remove the data 

x = df_results['raceId'].unique()

y = df_qualifying['raceId'].unique()

np.where(np.isin(x, y) == False)

df_results = df_results[df_results['raceId'].isin(y)]

x = df_results['raceId'].unique()

#Now we can combine the race data and quali data together into one dataframe

df = pd.merge(df_results, df_qualifying,  how='left', left_on=['raceId','driverId'], right_on = ['raceId','driverId'])

df = df.drop(['year_y', 'constructorId', 'qualifyId', 'number'], axis = 1)

df = df.rename(columns={'year_x' : 'year', 'position' : 'qualiResultPosition'})

#Adding the drivers nationality to the dataframe to add another data point for the machine learning model

df = df.merge(df_drivers.loc[:,['driverId', 'nationality']],how='left', on='driverId')

#There are instances where the nationality of the driver is unknown

df.head(10)

#PROBLEM: How many drivers didn't set a time in q1 (= no pace established in quali)

df = df.replace('\\N', np.nan)

# print("No lap time in q1 set: ", df['q1'].isnull().values.sum())

df = df[df['q1'].notnull()]

# print("No lap time in q1 set (after removing): ", df['q1'].isnull().values.sum())

#PROBLEM: If a driver doesn't advance to the next round of quali, they don't set a lap time

df = df.fillna(0)

# print("Null values in dataframe: ",df.isnull().values.any())

#PROBLEM: splitting lap time strings into format [min, sec, msec]


def get_time_lst(df, col):
    
    col_lst = df[col].str.split(pat=r':|\.').fillna(0)
    
    return col_lst


df['q1_lst'] = get_time_lst(df, 'q1')
df['q2_lst'] = get_time_lst(df, 'q2')
df['q3_lst'] = get_time_lst(df, 'q3')


# print("Null values in dataframe: ",df.isnull().values.any())

def convert_to_msec(time_lst):
    
    if time_lst != 0:
    
        return int(time_lst[0])*60000 + int(time_lst[1])*1000 + int(time_lst[2])
    
    return 0

df['q1Msec'] = df.apply(lambda x: convert_to_msec(x['q1_lst']), axis=1)
df['q2Msec'] = df.apply(lambda x: convert_to_msec(x['q2_lst']), axis=1)
df['q3Msec'] = df.apply(lambda x: convert_to_msec(x['q3_lst']), axis=1)


# print("Null values in dataframe (added q_Msec): ",df.isnull().values.any())


#df = df.loc[:,['raceId', 'qualifyId', 'driverId', 'position', 'year', 'q1Msec', 'q2Msec', 'q3Msec']]

#ADD: Max Pace in session

df['maxPace'] = df.loc[:, ['q1Msec', 'q2Msec', 'q3Msec']].max(axis=1)

# print("Null values in dataframe (added maxPace): ",df.isnull().values.any())

#ADD: Mean Pace per session

df['meanPace'] = df.loc[:, ['q1Msec', 'q2Msec', 'q3Msec']].sum(axis=1) / (df.loc[:, ['q1Msec', 'q2Msec', 'q3Msec']] != 0).sum(axis=1)

# print("Null values in dataframe (added meanPace): ",df.isnull().values.any())

df = df.drop(['q1_lst', 'q2_lst', 'q3_lst', 'q1', 'q2', 'q3'], axis = 1)

df.head(10)

#ADD: Drivers' expeirence that increases every year

df['driverExpYears'] = df['year'] - df['yearStarted']

df[df['driverId'] == 9]

def XGBoost_model_train(X, Y, test_size=0.2, cv=10):
    # Split the dataset into training and testing sets
    # X_train, X_test, Y_train, Y_test = train_test_split(X, Y, test_size=test_size, random_state=42)

    # Initialize the XGBoost model
    model = xgb.XGBClassifier(objective="multi:softmax", num_class=len(set(Y)), random_state=42)

    # Cross-validation to evaluate model performance
    cv_scores = cross_val_score(model, X, Y, cv=cv, scoring='accuracy')
    # print("Cross-Validation Scores:", cv_scores)
    logger.debug("Mean Accuracy:", np.mean(cv_scores))

    #Fit the model on the training set
    model.fit(X, Y)
    accuracy = round(np.mean(cv_scores)*100)

    return model, accuracy

def getRacePredictions():
    # Feature set (X) and target (Y)
    X = df[['startingPosition', 'driverExpYears', 'meanPace', 'maxPace']]  # Select features
    Y_position = df["racePosition"] - 1  # Adjust Y if necessary

    # Call the XGBoost model
    # Assume X and Y_position are already defined
    model, accuracy = XGBoost_model_train(X, Y_position)


    # Next Race Prediction
    X_test = X.tail(10)
    X_full = df.tail(10)

    X_full['predict'] = model.predict(X_test) + 1

    # Create a dictionary to map driverId to the driver's code (or forename/surname as needed)
    df_drivers['driverCode'] = df_drivers['code']  # Assuming 'code' is something like 'Lec', 'Ver', etc.
    driver_id_to_code = df_drivers.set_index('driverId')['driverCode'].to_dict()

    # Make predictions on the last 10 records (or X_test)
    X_test = X.tail(20)  # Feature set for the last 10 races
    X_full = df.tail(20)  # Full dataset with corresponding information

    # Predict race positions
    X_full['predict'] = model.predict(X_test) + 1  # Add 1 to revert to original race positions

    # Create a list of dictionaries for driver predictions with certainty and rank

    predictions_output = []

    for idx, row in X_full.iterrows():
        driver_id = row['driverId']  # Get the driver ID from the row
        driver_code = driver_id_to_code.get(driver_id, "Unknown Driver")  # Map to driver code
        predicted_position = row['predict']  # Get the predicted position
        # Create the dictionary for each driver
        driver_prediction = {
            'driver': driver_code,
            'rank': str(predicted_position)
        }
        
        # Append to the list
        predictions_output.append(driver_prediction)
    predictions_output.sort(key=sortRank)
    #Change order so that there isn't duplicates of pecking order
    n = 1
    for e in predictions_output:
        e['rank'] = n
        n+=1

    # Print the list of predictions in order
    # print(f"The accuracy is: {accuracy}")
    return predictions_output, accuracy

def sortRank(driver_prediction):
    return int(driver_prediction['rank'])

if __name__ == '__main__':
    logger.info('Starting up...')
    logger.info(getRacePredictions())
    logger.info('Shutting down...')