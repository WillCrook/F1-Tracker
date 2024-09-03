"""
Will Crook
Sept 24

"""
import fastf1
from loguru import logger
from pprint import pprint
from datetime import datetime


def getUpcomingGrandPrix():
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
    up_gp = fastf1.get_events_remaining().iloc[0].to_dict()
    up_gp_list = []
    for element in ['EventName', 'Location', 'RoundNumber', 'EventDate']:
        up_gp_list.append(up_gp[element])
    return up_gp_list


@logger.catch
def main():
    pprint(fastf1.get_events_remaining().iloc[0].to_dict())
    

if __name__ == "__main__":
    main()