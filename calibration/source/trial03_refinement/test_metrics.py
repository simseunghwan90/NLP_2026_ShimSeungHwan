import numpy as np
from metrics import turns

def test_complete_missing_revolution_is_not_wrapped_away():
    observed=np.linspace(0,4*np.pi,1001)
    native=np.linspace(0,2*np.pi,1001)
    a,b=turns(np.angle(np.exp(1j*observed)),np.angle(np.exp(1j*native)))
    assert abs(a-2)<1e-12 and abs(b-1)<1e-12

def test_right_turn_and_initial_heading_offset():
    a,b=turns(np.linspace(2,2-3*np.pi,1001),np.linspace(-1,-1-2*np.pi,1001))
    assert abs(a+1.5)<1e-12 and abs(b+1)<1e-12
