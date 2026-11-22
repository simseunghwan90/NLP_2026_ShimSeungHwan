"""Recorded-input validation for the declared full maneuvers (up to 600s for the full LAT6 record)."""
import numpy as np

def validate_case(config):
    c=np.asarray(config["commands"],dtype=float)
    duration=config["duration_s"]
    if config["lift"] is not False or not np.isfinite(duration) or not 0<duration<=600:
        raise ValueError("Invalid ground fixture/duration")
    if c.ndim!=2 or c.shape[1]!=5 or len(c)<1 or not np.isfinite(c).all():
        raise ValueError("Invalid command rows")
    if c[0,0]!=0 or c[-1,0]>duration or np.any(np.diff(c[:,0])<=0):
        raise ValueError("Invalid command time")
    if np.any((c[:,1:3]<0)|(c[:,1:3]>100)) or np.any(abs(c[:,3])>150):
        raise ValueError("Command outside DBC units/range")
    if np.any((c[:,4]<0)|(c[:,4]>7)|(c[:,4]!=np.floor(c[:,4]))):
        raise ValueError("Invalid automatic mode bits")
