import fastf1
import fastf1.mvapi
from loguru import logger
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from io import BytesIO
import fastf1.plotting
import pandas as pd
from timple.timedelta import strftimedelta
from fastf1.core import Laps
import matplotlib
import seaborn as sns
import numpy as np
from matplotlib import colormaps
from matplotlib.collections import LineCollection
from abc import ABC, abstractmethod
from f1Tracker import ml
from datetime import timedelta

#set matplotlib to non GUI to save resources
matplotlib.use('Agg')

class F1Data(ABC):
    def __init__(self):
        try:
            #set the year 
            self.year = 2024

            #get remaining events
            remaining_events = fastf1.get_events_remaining()
            if not remaining_events.empty:
                self.upcoming_event = remaining_events.iloc[0].to_dict()
                logger.info(f"The upcoming event {self.upcoming_event} is being used")
            else:
                self.upcoming_event = None
                logger.warning("No upcoming events found.")

            #get event schedule
            event_schedule = fastf1.get_event_schedule(self.year)
            if 'EventName' in event_schedule:
                self.events = event_schedule['EventName'].to_dict()
                logger.info(f"Events: {self.events}")
            else:
                self.events = {}
                logger.warning("Unable to get events.")

            #calculate the previous round number 
            #if there is no upcoming event or the upcoming event is into the next season then the last event gets picked
            if (self.upcoming_event == None) or ("2025" in str(self.upcoming_event.get("EventDate", 'N/A'))):
                self.previous_round_number = list(self.events.keys())[-1]
            else:
                self.previous_round_number = (self.upcoming_event.get('RoundNumber', 1) - 1)

        except Exception as e:
            logger.error(f"Error retrieving F1 data: {e}")
            self.upcoming_event = None
            self.events = {}
            self.previous_round_number = None
        
    def get_events(self):
        try:
            #filter and reverse events
            event = []
            for round_number, event_data in self.events.items():
                if 0 < round_number <= self.previous_round_number:
                     event.append(event_data)
            event.reverse()

            logger.info(f"Events for graphs: {event}")
            return event
        
        except Exception as e:
            logger.error(f"Error in get_events: {e}")
            return ["Error retrieving events"]

    def get_last_grand_prix(self):
        return self.previous_round_number
    
    @abstractmethod
    def predictions(self):
        """
        Abstract method for making the machine learning predictions for both the race and quali
        Must be implemented by subclasses
        """
        pass
    
class F1RaceData(F1Data):  

    def __init__(self):
        super().__init__()
        self.session_type = 'R'

    def predictions(self):
        return ml.getRacePredictions()

    def get_positions_change_during_a_race(self, grand_prix):
        fastf1.plotting.setup_mpl(mpl_timedelta_support=True, misc_mpl_mods=False,
                          color_scheme='fastf1')
        
        #load the session for the current round
        session = fastf1.get_session(self.year, grand_prix, self.session_type)
        session.load(telemetry=False, weather=False)

        #create the figure and axis
        fig, ax = plt.subplots(figsize=(15, 10))

        #plot driver positions
        for driver in session.drivers:
            driver_laps = session.laps.pick_driver(driver)
            driver_code = driver_laps['Driver'].iloc[0]  # Get driver abbreviation
            style = fastf1.plotting.get_driver_style(identifier=driver_code,
                                             style=['color', 'linestyle'],
                                             session=session)
            
            ax.plot(driver_laps['LapNumber'], driver_laps['Position'], label=driver_code, **style)

        #customize the plot axis
        ax.set_ylim([20.5, 0.5])
        ax.set_yticks([1, 5, 10, 15, 20])
        ax.set_xlabel('Lap')
        ax.set_ylabel('Position')
        ax.legend(bbox_to_anchor=(1.0, 1.02))

        #set title
        plt.suptitle(f"{session.event['EventName']} {self.year} Positions Changed During a Race")

        buf = BytesIO()
        fig.savefig(buf, format="png")
        buf.seek(0)
        plt.close(fig)
        return buf
    
    def get_team_pace_comparison(self, grand_prix):
        #load FastF1's dark color scheme
        fastf1.plotting.setup_mpl(mpl_timedelta_support=False, misc_mpl_mods=False,
                          color_scheme='fastf1')
        
        #choose race laps (within 107% of fastest lap so that slow laps don't skew the data).
        #for races with mixed conditions the slowest part of the session will be excluded
        session = fastf1.get_session(self.year, grand_prix, self.session_type)
        session.load()
        laps = session.laps.pick_quicklaps()

        #convert the lap time column from timedelta to integer.
        transformed_laps = laps.copy()
        transformed_laps.loc[:, "LapTime (s)"] = laps["LapTime"].dt.total_seconds()

        #order the team from the fastest (lowest median lap time excluding slow laps) to the slowest 
        team_order = (
            transformed_laps[["Team", "LapTime (s)"]]
            .groupby("Team")
            .median()["LapTime (s)"]
            .sort_values()
            .index
        )

        #make a color palette associating team names to hex codes
        team_palette = {team: fastf1.plotting.get_team_color(team, session=session)
                        for team in team_order}

    
        fig, ax = plt.subplots(figsize=(15, 10))
        sns.boxplot(
            data=transformed_laps,
            x="Team",
            y="LapTime (s)",
            hue="Team",
            order=team_order,
            palette=team_palette,
            whiskerprops=dict(color="white"),
            boxprops=dict(edgecolor="white"),
            medianprops=dict(color="grey"),
            capprops=dict(color="white"),
        )

        plt.suptitle(f"{self.year} {session.event['EventName']} Team Pace Comparison")
        plt.grid(visible=False)

        #x axis is doesn't do anything for team pace comparison as it is just a comparison and so its all relative
        ax.set(xlabel=None)
        plt.tight_layout()
        buf = BytesIO()
        fig.savefig(buf, format="png")
        buf.seek(0)
        plt.close(fig)
        return buf

    def get_driver_laptime_comparison(self,grand_prix):
        #enable Matplotlib patches for plotting timedelta values and load
        #fastF1's dark color scheme
        fastf1.plotting.setup_mpl(mpl_timedelta_support=True, misc_mpl_mods=False,
                                color_scheme='fastf1')


        #load the race session

        race = fastf1.get_session(self.year, grand_prix , self.session_type)
        race.load()

  
        #get laps for top 10 (points).
        #remove slow laps (eg. yellow flag, VSC, SC, pitstops etc.) as they make the graph axis look whack.
        point_finishers = race.drivers[:10]
        driver_laps = race.laps.pick_drivers(point_finishers).pick_quicklaps()
        driver_laps = driver_laps.reset_index()

        #get driver codes in the finishing order do display them on the graph.
        finishing_order = [race.get_driver(i)["Abbreviation"] for i in point_finishers]

        #violin plots to show the distributions then I use swarm plot to show the actual laptimes.
        #create the figure
        fig, ax = plt.subplots(figsize=(15, 10))

        #convert timedelta to float (in seconds) for seaborn
        driver_laps["LapTime(s)"] = driver_laps["LapTime"].dt.total_seconds()

        sns.violinplot(data=driver_laps,
                    x="Driver",
                    y="LapTime(s)",
                    hue="Driver",
                    inner=None,
                    density_norm="area",
                    order=finishing_order,
                    palette=fastf1.plotting.get_driver_color_mapping(session=race)
                    )

        sns.swarmplot(data=driver_laps,
                    x="Driver",
                    y="LapTime(s)",
                    order=finishing_order,
                    hue="Compound",
                    palette=fastf1.plotting.get_compound_mapping(session=race),
                    hue_order=["SOFT", "MEDIUM", "HARD"],
                    linewidth=0,
                    size=4,
                    )
       
        #make the plot more aesthetic
        ax.set_xlabel("Driver")
        ax.set_ylabel("Lap Time (s)")
        plt.suptitle(f"{self.year} {grand_prix} Lap Time Distributions")
        sns.despine(left=True, bottom=True)

        plt.tight_layout()
        buf = BytesIO()
        fig.savefig(buf, format="png")
        buf.seek(0)
        plt.close(fig)
        return buf
    
    def get_tyre_strategies(self, grand_prix):

        #load the race session
        session = fastf1.get_session(self.year, grand_prix, self.session_type)
        session.load()
        laps = session.laps

        
        #get the list of driver numbers
        drivers = session.drivers

        #convert the driver numbers to three letter abbreviations
        drivers = [session.get_driver(driver)["Abbreviation"] for driver in drivers]

        #works out the stint length and compound used for every stint by every driver 
        stints = laps[["Driver", "Stint", "Compound", "LapNumber"]]
        stints = stints.groupby(["Driver", "Stint", "Compound"]) #groups same values in each column
        stints = stints.count().reset_index() #pandas function to count each row and then converts into 0 indexing

        #the number in the LapNumber column now stands for the number of observations
        #in that group aka the stint length.
        stints = stints.rename(columns={"LapNumber": "StintLength"})

        #now we can plot the strategies for each driver
        fig, ax = plt.subplots(figsize=(15, 10))

        for driver in drivers:
            driver_stints = stints.loc[stints["Driver"] == driver]

            previous_stint_end = 0
            for idx, row in driver_stints.iterrows():
                #each row contains the compound name and stint length
                #we can use these information to draw horizontal bars
                compound_color = fastf1.plotting.get_compound_color(row["Compound"],
                                                                    session=session)
                plt.barh(
                    y=driver,
                    width=row["StintLength"],
                    left=previous_stint_end,
                    color=compound_color,
                    edgecolor="black",
                    fill=True
                )

                previous_stint_end += row["StintLength"]
                
        #make the plot more readable and intuitive
        plt.suptitle(f"{self.year} {session.event['EventName']} Strategies")
        plt.xlabel("Lap Number")
        plt.grid(False)
        #invert the y-axis so drivers that finish higher are closer to the top
        ax.invert_yaxis()

        #plot aesthetics
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)

        plt.tight_layout()
        buf = BytesIO()
        fig.savefig(buf, format="png")
        buf.seek(0)
        plt.close(fig)
        return buf

class F1QualiData(F1Data):

    def __init__(self):
        super().__init__()
        self.session_type = 'Q'

    def predictions(self):
        return ml.getQualiPredictions()

    def get_quali_results_overview(self, grand_prix):
        fastf1.plotting.setup_mpl(mpl_timedelta_support=True, misc_mpl_mods=False, color_scheme='fastf1')
        
        session = fastf1.get_session(self.year, grand_prix, self.session_type)
        session.load()
        drivers = pd.unique(session.laps['Driver'])
        logger.debug(drivers)

        list_fastest_laps = list()
        for drv in drivers:
            drvs_fastest_lap = session.laps.pick_driver(drv).pick_fastest()
            list_fastest_laps.append(drvs_fastest_lap)

        fastest_laps = Laps(list_fastest_laps) \
            .sort_values(by='LapTime') \
            .reset_index(drop=True)
        pole_lap = fastest_laps.pick_fastest()
        fastest_laps['LapTimeDelta'] = fastest_laps['LapTime'] - pole_lap['LapTime']
        logger.debug(fastest_laps[['Driver', 'LapTime', 'LapTimeDelta']])

        team_colors = list()
        for index, lap in fastest_laps.iterlaps():
            color = fastf1.plotting.get_team_color(lap['Team'], session=session)
            team_colors.append(color)

        fig, ax = plt.subplots(figsize=(15, 10))

        ax.barh(fastest_laps.index, fastest_laps['LapTimeDelta'],
                color=team_colors, edgecolor='grey')
        ax.set_yticks(fastest_laps.index)
        ax.set_yticklabels(fastest_laps['Driver'])

        #show fastest at the top
        ax.invert_yaxis()

        #draw vertical lines behind the bars
        ax.set_axisbelow(True)
        ax.xaxis.grid(True, which='major', linestyle='--', color='black', zorder=-1000)

        lap_time_string = strftimedelta(pole_lap['LapTime'], '%m:%s.%ms')

        plt.suptitle(f"{session.event['EventName']} {self.year} Qualifying\n"
                    f"Fastest Lap: {lap_time_string} ({pole_lap['Driver']})")

        buf = BytesIO()
        fig.savefig(buf, format="png")
        buf.seek(0)
        plt.close(fig)
        return buf
    
    def get_gear_shifts(self,grand_prix):
        
        #enable Matplotlib patches for plotting timedelta values and load
        #load FastF1's dark color scheme to fit colour scheme
        fastf1.plotting.setup_mpl(mpl_timedelta_support=False, misc_mpl_mods=False,
                            color_scheme='fastf1')
        session = fastf1.get_session(self.year, grand_prix, self.session_type)
        session.load()

        lap = session.laps.pick_fastest()
        tel = lap.get_telemetry()
       
        #prepare the data for plotting by converting it to the appropriate numpy data types

        x = np.array(tel['X'].values)
        y = np.array(tel['Y'].values)

        points = np.array([x, y]).T.reshape(-1, 1, 2)
        segments = np.concatenate([points[:-1], points[1:]], axis=1)
        gear = tel['nGear'].to_numpy().astype(float)

        #create figure and axis
        fig, ax = plt.subplots(figsize=(15, 10))
    
        #create a line collection. Set a segmented colormap and normalize the plot
        #to full integer values of the colormap

        cmap = colormaps['Paired']
        lc_comp = LineCollection(segments, norm=plt.Normalize(1, cmap.N+1), cmap=cmap)
        lc_comp.set_array(gear)
        lc_comp.set_linewidth(4)

        #plot        
        plt.gca().add_collection(lc_comp)
        plt.axis('equal')
        plt.tick_params(labelleft=False, left=False, labelbottom=False, bottom=False)

        plt.suptitle(
            f"Fastest Lap Gear Shift Visualization\n"
            f"{lap['Driver']} - {session.event['EventName']} {self.year}"
        )
        
        #add a colorbar to the plot. Shift the colorbar ticks by +0.5 so that they
        #are centered for each color segment.

        cbar = plt.colorbar(mappable=lc_comp, label="Gear",
                            boundaries=np.arange(1, 10))
        cbar.set_ticks(np.arange(1.5, 9.5))
        cbar.set_ticklabels(np.arange(1, 9))


        buf = BytesIO()
        fig.savefig(buf, format="png")
        buf.seek(0)
        plt.close(fig)
        return buf

#this allows other classes to use the F1Data class without having to implement the predictions method
class CoreF1Data(F1Data):
    def predictions(self):
        #placeholder implementation to allow other classes to use F1Data without the predictions method
        pass

class F1UpcomingData():
    def __init__(self):
        self.f1_data = CoreF1Data()

    def get_upcoming_grand_prix(self):
        return self.f1_data.upcoming_event.get('EventName', 'N/A')

    def get_countdown_date(self):
        return self.f1_data.upcoming_event.get('EventDate', 'N/A')

    def get_upcoming_grand_prix_info(self):
        #upcoming Grand Prix works by always returning the "error retrieving upcoming Grand Prix info"
        #if there is any issue to the user. I have also implemented logs throughout so that the admin can
        #can see on there end where the problem actually lies. This would show whether its an API issue or it's just because its the end of the season. 
        logger.info("Retrieving upcoming Grand Prix info...")
        
        #check to see if there is an upcoming Grand Prix
        if not self.f1_data.upcoming_event:
            logger.error("No upcoming event available.")
            return ["No Upcoming Grand Prix Avalaible"]

        try:
            upcoming_event = self.f1_data.upcoming_event
            date = upcoming_event.get('EventDate', 'N/A')

            if not date:
                logger.error("Missing 'EventDate' in upcoming event.")
                return ["Error retrieving upcoming Grand Prix info"]

            
            try:
                if "Testing" in upcoming_event.get('EventName', 'N/A'):
                    test_number = 1  
                    session_number = 1  
                    testing_session = fastf1.get_testing_session(self.f1_data.year, test_number, session_number)
                    testing_session.load(laps=True, telemetry=False, weather=False, messages=False)
                    fastest_lap = testing_session.laps.pick_fastest().to_dict()
                    lap_time = fastest_lap.get('LapTime', 'N/A')
                    circuit_info = testing_session.get_circuit_info()
                    corners = circuit_info.corners
                    corner_count = len(corners)
                    
                else:
                    last_circuit_info = fastf1.get_session((int(self.f1_data.year)), upcoming_event['RoundNumber'], 'R')
                    last_circuit_info.load(laps=True, telemetry=False, weather=False, messages=False)
                    fastest_lap = last_circuit_info.laps.pick_fastest().to_dict()
                    lap_time = fastest_lap.get('LapTime', 'N/A')
                    circuit_info = last_circuit_info.get_circuit_info()
                    corners = circuit_info.corners
                    corner_count = len(corners)
                

                #convert to how it would look like a standard laptime in F1
                if isinstance(lap_time, timedelta):
                    minutes = lap_time.seconds // 60
                    seconds = lap_time.seconds % 60
                    milliseconds = lap_time.microseconds // 1000
                    formatted_time = f"{minutes}:{seconds}.{milliseconds:03}"
                else:
                    formatted_time = 'N/A'
                
                
                
            except Exception as e:
                logger.error(f"Error loading last session info: {e}")

            return [
                    f"Event Name: {upcoming_event.get('EventName', 'N/A')}",
                    f"Event Date: {upcoming_event.get('EventDate', 'N/A')}",
                    f"Location: {upcoming_event.get('Location', 'N/A')}",
                    f"Round Number: {upcoming_event.get('RoundNumber', 'N/A')}",
                    f"Fastest Driver last year was {fastest_lap.get('Driver', 'N/A')} with a time of: {formatted_time}",
                    f"Number of Corners: {corner_count}"
                    ]


        except Exception as e:
            logger.error(f"Error in get_upcoming_grand_prix_info: {e}")

        return ["Error retrieving upcoming Grand Prix info"]