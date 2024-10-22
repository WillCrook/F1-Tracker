import fastf1
from loguru import logger
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from io import BytesIO
import base64
import fastf1.plotting

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
        # Load the session for the current round
        session = fastf1.get_session(self.year, grand_prix, 'R')
        session.load(telemetry=False, weather=False)

        # Create the figure and axis
        fig = Figure(figsize=(8.0, 4.9))
        ax = fig.subplots()

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
        
