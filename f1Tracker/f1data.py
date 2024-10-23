import fastf1
from loguru import logger
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from io import BytesIO
import base64
import fastf1.plotting
import pandas as pd
from timple.timedelta import strftimedelta
from fastf1.core import Laps
import matplotlib
import seaborn as sns
import numpy as np
from matplotlib import colormaps
from matplotlib.collections import LineCollection

#set matplotlib to non gui to save resources
matplotlib.use('Agg')

class F1Data:
    def __init__(self):
        try:
            self.year = 2024
            self.upcoming_event = fastf1.get_events_remaining().iloc[0].to_dict()
            eventSchedule = fastf1.get_event_schedule(self.year)
            logger.info(f'events: {eventSchedule.to_dict()['EventName']}')

            self.events = eventSchedule.to_dict()['EventName']
            self.previous_round_number = self.upcoming_event['RoundNumber'] - 1
            
        except Exception as e:
            logger.error(f"Error retrieving F1 data: {e}")
            return ["Unable to retrieve F1 Data", "Error"]
        
    
    def get_events(self):
        event = [event for round, event in self.events.items() if 0 < round <= self.previous_round_number]
        event.reverse()
        return event

    def get_positions_change_during_a_race(self, grand_prix):
        fastf1.plotting.setup_mpl(mpl_timedelta_support=True, misc_mpl_mods=False,
                          color_scheme='fastf1')
        
        # Load the session for the current round
        session = fastf1.get_session(self.year, grand_prix, 'R')
        session.load(telemetry=False, weather=False)

        # Create the figure and axis
        fig, ax = plt.subplots(figsize=(15, 10))

        # Plot driver positions
        for drv in session.drivers:
            drv_laps = session.laps.pick_driver(drv)
            abb = drv_laps['Driver'].iloc[0]  # Get driver abbreviation
            style = fastf1.plotting.get_driver_style(identifier=abb,
                                             style=['color', 'linestyle'],
                                             session=session)
            
            ax.plot(drv_laps['LapNumber'], drv_laps['Position'], label=abb, **style)

        # Customize the plot
        ax.set_ylim([20.5, 0.5])
        ax.set_yticks([1, 5, 10, 15, 20])
        ax.set_xlabel('Lap')
        ax.set_ylabel('Position')
        ax.legend(bbox_to_anchor=(1.0, 1.02))

        buf = BytesIO()
        fig.savefig(buf, format="png")
        buf.seek(0)
        plt.close(fig)
        return buf
    
    def get_quali_results_overview(self, grand_prix):
        fastf1.plotting.setup_mpl(mpl_timedelta_support=True, misc_mpl_mods=False,
                          color_scheme='fastf1')
        
        session = fastf1.get_session(self.year, grand_prix, 'Q')
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

        # show fastest at the top
        ax.invert_yaxis()

        # draw vertical lines behind the bars
        ax.set_axisbelow(True)
        ax.xaxis.grid(True, which='major', linestyle='--', color='black', zorder=-1000)

        lap_time_string = strftimedelta(pole_lap['LapTime'], '%m:%s.%ms')

        plt.suptitle(f"{session.event['EventName']} {session.event.year} Qualifying\n"
                    f"Fastest Lap: {lap_time_string} ({pole_lap['Driver']})")

        buf = BytesIO()
        fig.savefig(buf, format="png")
        buf.seek(0)
        plt.close(fig)
        return buf
    
    def get_team_pace_comparison(self, grand_prix):
        # Load FastF1's dark color scheme
        fastf1.plotting.setup_mpl(mpl_timedelta_support=False, misc_mpl_mods=False,
                          color_scheme='fastf1')
        
        # Load the race session.
        # Pick all quick laps (within 107% of fastest lap).
        # For races with mixed conditions, pick_wo_box() is better.
        race = fastf1.get_session(self.year, grand_prix, 'R')
        race.load()
        laps = race.laps.pick_quicklaps()

        # Convert the lap time column from timedelta to integer.
        transformed_laps = laps.copy()
        transformed_laps.loc[:, "LapTime (s)"] = laps["LapTime"].dt.total_seconds()

        # order the team from the fastest (lowest median lap time) tp slower
        team_order = (
            transformed_laps[["Team", "LapTime (s)"]]
            .groupby("Team")
            .median()["LapTime (s)"]
            .sort_values()
            .index
        )
        print(team_order)

        # make a color palette associating team names to hex codes
        team_palette = {team: fastf1.plotting.get_team_color(team, session=race)
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

        plt.title(f"{self.year} {grand_prix}")
        plt.grid(visible=False)

        # x-label is redundant
        ax.set(xlabel=None)
        plt.tight_layout()
        buf = BytesIO()
        fig.savefig(buf, format="png")
        buf.seek(0)
        plt.close(fig)
        return buf

    def get_gear_shifts(self,grand_prix):
        
        #   Enable Matplotlib patches for plotting timedelta values and load
        # Load FastF1's dark color scheme
        fastf1.plotting.setup_mpl(mpl_timedelta_support=False, misc_mpl_mods=False,
                            color_scheme='fastf1')
        session = fastf1.get_session(self.year, grand_prix, 'Q')
        session.load()

        lap = session.laps.pick_fastest()
        tel = lap.get_telemetry()
        # sphinx_gallery_defer_figures

        ##############################################################################
        # Prepare the data for plotting by converting it to the appropriate numpy
        # data types

        x = np.array(tel['X'].values)
        y = np.array(tel['Y'].values)

        points = np.array([x, y]).T.reshape(-1, 1, 2)
        segments = np.concatenate([points[:-1], points[1:]], axis=1)
        gear = tel['nGear'].to_numpy().astype(float)
        # sphinx_gallery_defer_figures

        #create figure and axis
        fig, ax = plt.subplots(figsize=(15, 10))
    
        # Create a line collection. Set a segmented colormap and normalize the plot
        # to full integer values of the colormap

        cmap = colormaps['Paired']
        lc_comp = LineCollection(segments, norm=plt.Normalize(1, cmap.N+1), cmap=cmap)
        lc_comp.set_array(gear)
        lc_comp.set_linewidth(4)
        # sphinx_gallery_defer_figures

        # Create the plot
        
        plt.gca().add_collection(lc_comp)
        plt.axis('equal')
        plt.tick_params(labelleft=False, left=False, labelbottom=False, bottom=False)

        plt.suptitle(
            f"Fastest Lap Gear Shift Visualization\n"
            f"{lap['Driver']} - {session.event['EventName']} {session.event.year}"
        )
        # sphinx_gallery_defer_figures

        # Add a colorbar to the plot. Shift the colorbar ticks by +0.5 so that they
        # are centered for each color segment.

        cbar = plt.colorbar(mappable=lc_comp, label="Gear",
                            boundaries=np.arange(1, 10))
        cbar.set_ticks(np.arange(1.5, 9.5))
        cbar.set_ticklabels(np.arange(1, 9))


        buf = BytesIO()
        fig.savefig(buf, format="png")
        buf.seek(0)
        plt.close(fig)
        return buf

    def get_driver_laptime_comparison(self,grand_prix):
        # Enable Matplotlib patches for plotting timedelta values and load
        # FastF1's dark color scheme
        fastf1.plotting.setup_mpl(mpl_timedelta_support=True, misc_mpl_mods=False,
                                color_scheme='fastf1')


        # Load the race session

        race = fastf1.get_session(self.year, grand_prix , 'R')
        race.load()

  
        # Get all the laps for the point finishers only.
        # Filter out slow laps (yellow flag, VSC, pitstops etc.)
        # as they distort the graph axis.
        point_finishers = race.drivers[:10]
        print(point_finishers)
        driver_laps = race.laps.pick_drivers(point_finishers).pick_quicklaps()
        driver_laps = driver_laps.reset_index()

        # To plot the drivers by finishing order,
        # we need to get their three-letter abbreviations in the finishing order.
        finishing_order = [race.get_driver(i)["Abbreviation"] for i in point_finishers]
        print(finishing_order)

        # First create the violin plots to show the distributions.
        # Then use the swarm plot to show the actual laptimes.

        # create the figure
        fig, ax = plt.subplots(figsize=(15, 10))

        # Seaborn doesn't have proper timedelta support,
        # so we have to convert timedelta to float (in seconds)
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
        # sphinx_gallery_defer_figures

        
        # Make the plot more aesthetic
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

        # Load the race session

        session = fastf1.get_session(self.year, grand_prix, 'R')
        session.load()
        laps = session.laps

        
        # Get the list of driver numbers
        drivers = session.drivers
        print(drivers)

        # Convert the driver numbers to three letter abbreviations
        drivers = [session.get_driver(driver)["Abbreviation"] for driver in drivers]
        print(drivers)

        # We need to find the stint length and compound used
        # for every stint by every driver.
        # We do this by first grouping the laps by the driver,
        # the stint number, and the compound.
        # And then counting the number of laps in each group.
        stints = laps[["Driver", "Stint", "Compound", "LapNumber"]]
        stints = stints.groupby(["Driver", "Stint", "Compound"])
        stints = stints.count().reset_index()

        # The number in the LapNumber column now stands for the number of observations
        # in that group aka the stint length.
        stints = stints.rename(columns={"LapNumber": "StintLength"})
        print(stints)

        # Now we can plot the strategies for each driver
        fig, ax = plt.subplots(figsize=(15, 10))

        for driver in drivers:
            driver_stints = stints.loc[stints["Driver"] == driver]

            previous_stint_end = 0
            for idx, row in driver_stints.iterrows():
                # each row contains the compound name and stint length
                # we can use these information to draw horizontal bars
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

        # sphinx_gallery_defer_figures

        # Make the plot more readable and intuitive
        plt.title(f"{self.year} {grand_prix} Strategies")
        plt.xlabel("Lap Number")
        plt.grid(False)
        # invert the y-axis so drivers that finish higher are closer to the top
        ax.invert_yaxis()

        # Plot aesthetics
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)

        plt.tight_layout()
        buf = BytesIO()
        fig.savefig(buf, format="png")
        buf.seek(0)
        plt.close(fig)
        return buf
    


    def get_upcoming_grand_prix_info(self):
       
        upcoming_event = self.upcoming_event
        up_gp_list = []
        date = upcoming_event['EventDate']

        # Load previous session info
        last_circuit_info = fastf1.get_session(date.year - 1, upcoming_event['EventName'], 'R')
        last_circuit_info.load(laps=True, telemetry=False, weather=False, messages=False)

        # Append last circuit info
        for element in ["Driver", "LapTime"]:
            up_gp_list.append(last_circuit_info.laps.pick_fastest().to_dict().get(element, "N/A"))
        
        # Append upcoming event details
        for element in ['EventName', 'Location', 'RoundNumber', 'EventDate']:
            up_gp_list.append(f'{element}: {upcoming_event[element]}')

        return up_gp_list 
        
