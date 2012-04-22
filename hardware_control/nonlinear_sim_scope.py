import os
import pco, dmd, stage, shutters, wheel

def initialize(micromirror_parameters):
    camera_parameters = {
            'trigger': "external trigger/software exposure control",
            'exposure_time_microseconds': 2200,
            }
    camera = pco.Edge()
    camera.apply_settings(**camera_parameters)
    camera.arm()
    micromirrors = dmd.Micromirror_Subprocess(**micromirror_parameters)
    laser_shutters = shutters.Laser_Shutters(colors=['561', '488'])
    filter_wheel = wheel.Filter_Wheel(initial_position='f3')
    return camera, micromirrors, laser_shutters, filter_wheel

def close(camera, micromirrors, laser_shutters, filter_wheel):
    laser_shutters.close()
    filter_wheel.close()
    camera.close()
    micromirrors.close()
    return None

micromirror_parameters = {
    'delay': 0.02,
    'illumination_filename': 'illumination_pattern.raw',
    'illuminate_time': 2200,
    'picture_time': 4500,
    }
camera, micromirrors, laser_shutters, filter_wheel = initialize(
    micromirror_parameters)
recording_parameters = {
    'num_images': micromirrors.num_images,
    'preframes': 3,
    'save_path': os.getcwd(),
    }
num_tries = 3

for color, filename, pattern in (
    ('488', 'bleachdown.raw', 'fat'), #488 bleachdown
    ('561', None, 'skinny'), #405 activation
    ('488', 'readout.raw', 'skinny'), #488 readout
    ):
    if pattern == 'fat':
        micromirror_parameters['illumination_filename'
                               ] = 'illumination_pattern.raw'
    elif pattern == 'skinny':
        micromirror_parameters['illumination_filename'
                               ] = 'illumination_pattern.raw'
    print micromirror_parameters
    micromirrors.apply_settings(**micromirror_parameters)
    recording_parameters['num_images'] = micromirrors.num_images
    recording_parameters['file_name'] = filename #A bunch of the same image
    for tries in range(num_tries):
        print "Triggering micromirrors..."
        laser_shutters.open(color)
        micromirrors.display_pattern()
        try:
            if filename is not None: #Don't bother to record the activation
                camera.record_to_file(**recording_parameters)
            break #It worked!
        except Exception as exc:
            print "\n Recording failed"
            close(camera, micromirrors, laser_shutters, filter_wheel)
            camera, micromirrors, laser_shutters, filter_wheel = initialize(
                micromirror_parameters)
    else: #We failed a bunch of times
        raise exc
    micromirrors.readout() #Wait for the DMD to finish displaying
    laser_shutters.shut(color)

close(camera, micromirrors, laser_shutters, filter_wheel)
