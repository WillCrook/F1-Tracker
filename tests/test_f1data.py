import pytest
from f1Tracker.f1data import getUpcomingGrandPrix

def test_upcoming():
    up_gp = getUpcomingGrandPrix()
    assert 'EventName' in up_gp