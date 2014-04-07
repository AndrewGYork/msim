import numpy as np
from daq import DAQ

rotations_per_second = 150
facets_per_rotation = 10
points_per_second = 500000

"""
This logic assumes we can get away with an integer number of triggers
per write; if we end up using a mirror with an odd number of sides, or
if the mirror isn't perfectly regular, we might have to always use an
integer number of rotations per write, not an integer number of
triggers per write.
"""
triggers_per_rotation = 2
triggers_per_second = triggers_per_rotation * rotations_per_second
points_per_trigger = points_per_second * (1.0 / triggers_per_second)
facets_per_second = rotations_per_second * facets_per_rotation
points_per_facet = points_per_second * (1.0 / facets_per_second)
print
print "Desired points per rotation:", points_per_trigger * triggers_per_rotation
print "Desired points per facet:", points_per_facet
points_per_facet = int(round(points_per_facet))
points_per_trigger = int(points_per_facet *
                         facets_per_rotation *
                         (1.0 / triggers_per_rotation))
print "Actual points per rotation:", points_per_trigger * triggers_per_rotation
print "Actual points per facet:", (points_per_trigger *
                                   triggers_per_rotation *
                                   (1.0 / facets_per_rotation))
print
print "Desired rotations per second:", rotations_per_second
rotations_per_second = (points_per_second *
                        (1.0 / (points_per_trigger * triggers_per_rotation)))
print "Actual rotations per second:", rotations_per_second
print 
points_per_write = points_per_second // 10
print "Desired write length:", points_per_write
rotations_per_write = points_per_write * 1.0 / (points_per_trigger *
                                                triggers_per_rotation)
rotations_per_write = int(round(rotations_per_write))
points_per_write = (points_per_trigger *
                    triggers_per_rotation *
                    rotations_per_write)
print "Actual write length:", points_per_write
print "Rotations per write:", rotations_per_write
triggers_per_write = triggers_per_rotation * rotations_per_write
print "Triggers per write:", triggers_per_write
print

daq = DAQ(rate=points_per_second, write_length=points_per_write)

wheel_signal = np.zeros(daq.write_length, dtype=np.float64)
for i in range(triggers_per_write):
    start = i * points_per_trigger
    stop = start + points_per_trigger // 2
    wheel_signal[start:stop] = 6
wheel_brake_signal = np.zeros(daq.write_length, dtype=np.float64)

laser_signal = np.zeros(daq.write_length, dtype=np.float64)
laser_duration = 1
print "Laser duration:", laser_duration * 1.0 / points_per_second, "seconds"
##Positive is up
laser_lag = 65
for i in range(rotations_per_write):
    for n in range(1):
        start = (i * points_per_trigger * triggers_per_rotation +
                 n * points_per_facet + 
                 laser_lag)
        stop = start + laser_duration
        laser_signal[start:stop] = 10

voltage = np.zeros_like(daq.voltage)
voltage[:, 0] = wheel_signal
voltage[:, 1] = wheel_brake_signal
voltage[:, 2] = 5 #focusing objective
voltage[:, 3] = 0 #murrrcle
voltage[:, 6] = laser_signal
voltage[:, 7] = laser_signal

daq.set_voltage(voltage)
daq.scan()
num_writes = 0
writes_per_change = 10
which_facet = 0
while True:
    try:
        daq.write_voltage()
        num_writes += 1
        print "Num writes:", num_writes
##        if num_writes % writes_per_change == writes_per_change - 1:
##            which_facet += 1
##            which_facet = which_facet % num_facets
##            print "Changing to facet", which_facet
##            voltage[:, 6] = lagged_laser_signals[which_facet]
##            voltage[:, 7] = lagged_laser_signals[which_facet]
##            daq.set_voltage(voltage)
    except KeyboardInterrupt:
        break
daq.stop_scan()
daq.close()
raw_input("Hit enter to continue...")
