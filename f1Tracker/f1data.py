"""
Will Crook
Sept 24

"""
import fastf1
from loguru import logger
from pprint import pprint
from datetime import datetime


def getUpcomingGrandPrixInfo():
    """
    [
        "Track Length: 5.9km",
        "Lap Record: 1m 15.082",
        "Most Pole Postions: Charles Leclerc(16)",
        "Most Wins: Charles Leclerc(16)",
        "Safety Car Probabillity: 50%",
        "Pit Stop Loss Time: 20 Seconds"
    ]
    """
    upcomingEvent = fastf1.get_events_remaining().iloc[0].to_dict()
    up_gp_list = []
    date = upcomingEvent['EventDate']
    lastCircuitInfo = fastf1.get_session((upcomingEvent['EventDate'].year)-1, upcomingEvent['EventName'], 'R')
    lastCircuitInfo.load(laps = True, telemetry = False, weather = False, messages = False)
    for element in ["Driver", "LapTime"]:
        up_gp_list.append(lastCircuitInfo.laps.pick_fastest().to_dict()[element])
    for element in ['EventName', 'Location', 'RoundNumber', 'EventDate']:
        up_gp_list.append(upcomingEvent[element])
    return up_gp_list 


print(getUpcomingGrandPrixInfo())
