import pytest
from f1Tracker import f1data

def test_upcoming():
    up_gp = f1data.getUpcomingGrandPrixInfo()
    assert type(up_gp) is list