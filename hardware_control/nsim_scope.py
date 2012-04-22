import os
import pco, dmd, stage, shutters, wheel

def initialize():
    camera_parameters = {
            'trigger': "external trigger/software exposure control",
            'exposure_time_microseconds': 2200,
            }
    camera = pco.Edge()
    camera.apply_settings(**camera_parameters)
    camera.arm()
    micromirror_parameters = {
        'delay': 0.02,
        'pattern': pattern,
        'illuminate_time': 2200,
        'picture_time': 4500,
        }
    micromirrors = dmd.Micromirror_Subprocess(**micromirror_parameters)
    laser_shutters = shutters.Laser_Shutters(colors=['405', '488'))
    filter_wheel = wheel.Filter_Wheel(initial_position='f3')
    return camera, micromirrors, laser_shutters, filter_wheel

def close(camera, micromirrors, laser_shutters, filter_wheel):
    laser_shutters.close()
    filter_wheel.close()
    camera.close()
    micromirrors.close()
    return None

camera, micromirrors, laser_shutters, filter_wheel = initialize()
preframes = 3
save_path = os.getcwd()

##488 bleachdown
file_name = 'bleachdown.raw'
laser_shutters.open('488')
micromirrors.display_pattern()
try:
    camera.record_to_file(
        num_images=micromirrors.num_images, preframes=preframes,
        file_name=file_name, save_path=save_path)
except Exception as exc:
    pass #Handle your biz

## (but only to trigger camera, use the same pattern every change)
## record bleachdown frames

##405 activation
## change to fat pattern
## open 405 shutter
## wait

##488 readout
## arm camera
## open 488 shutter
## change to skinny pattern many times
## (but only to trigger camera, use the same pattern every change)
## record readout frames

close(camera, micromirrors, laser_shutters, filter_wheel):
