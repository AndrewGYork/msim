import os, time
import pco, dmd, stage, shutters, wheel

def initialize(micromirror_parameters):
    camera_parameters = {
            'trigger': "external trigger/software exposure control",
            'exposure_time_microseconds': 6700,
            }
    camera = pco.Edge()
    camera.apply_settings(**camera_parameters)
    camera.arm()
    micromirrors = dmd.Micromirror_Subprocess(**micromirror_parameters)
    laser_shutters = shutters.Laser_Shutters(colors=['405', '488'])
    filter_wheel = wheel.Filter_Wheel(initial_position='f3')
    return camera, micromirrors, laser_shutters, filter_wheel

def close(camera, micromirrors, laser_shutters, filter_wheel):
    laser_shutters.close()
    filter_wheel.close()
    camera.close()
    micromirrors.close()
    return None

offset_mapping = {
    (0, 0): './nSIM/patterns/offset_p00_p00.raw',
    (1, 0): './nSIM/patterns/offset_p01_p00.raw',
    (-1, 0): './nSIM/patterns/offset_n01_p00.raw',
    (0, 1): './nSIM/patterns/offset_p00_p01.raw',
    (0, -1): './nSIM/patterns/offset_p00_n01.raw',
    (1, 1): './nSIM/patterns/offset_p01_p01.raw',
    (-1, -1): './nSIM/patterns/offset_n01_n01.raw',
    (1, -1): './nSIM/patterns/offset_p01_n01.raw',
    (-1, 1): './nSIM/patterns/offset_n01_p01.raw',
    (2, 0): './nSIM/patterns/offset_p02_p00.raw',
    (-2, 0): './nSIM/patterns/offset_n02_p00.raw',
    (0, 2): './nSIM/patterns/offset_p00_p02.raw',
    (0, -2): './nSIM/patterns/offset_p00_n02.raw',
    (4, 0): './nSIM/patterns/offset_p04_p00.raw',
    (-4, 0): './nSIM/patterns/offset_n04_p00.raw',
    (0, 4): './nSIM/patterns/offset_p00_p04.raw',
    (0, -4): './nSIM/patterns/offset_p00_n04.raw',
    }

micromirror_parameters = {
    'delay': 0.02,
    'illumination_filename': 'illumination_pattern.raw',
    'illuminate_time': 6700,
    'picture_time': 9000,
    }
camera, micromirrors, laser_shutters, filter_wheel = initialize(
    micromirror_parameters)
recording_parameters = {
    'num_images': micromirrors.num_images,
    'preframes': 80,
    'save_path': os.getcwd(),
    }
num_tries = 1

##for i in (-1, 0, 1):
##    for j in (-1, 0, 1):
for i, j, k in (
    (4, 0, 0),
    (-4, 0, 0),
    (0, 0, 0),
    (0, 4, 0),
    (0, -4, 0),
    (4, 0, 1),
    (-4, 0, 1),
    (0, 0, 1),
    (0, 4, 1),
    (0, -4, 1)
    ):
    for color, filename, pattern, dose in (
        ('488', 'nSIM/bleachdown/%i_%i_%i.raw'%(i, j, k), #488 bleachdown
         './nSIM/patterns/bleachdown.raw', 75),
        ('405', 'nSIM/activation/%i_%i_%i.raw'%(i, j, k), #405 activation
         offset_mapping[i, j], 1),
        ('488', 'nSIM/readout/%i_%i_%i.raw'%(i, j, k), #488 readout
         './nSIM/patterns/readout.raw', 50),
        ):
        if color == '405':
            print "Pausing..."
            time.sleep(0)
        micromirror_parameters['illumination_filename'] = pattern
        micromirror_parameters['first_frame']=3
        micromirror_parameters['last_frame']=3
        micromirror_parameters['repetitions']=dose
        micromirror_parameters['additional_preframes'
                               ] = recording_parameters['preframes']
        print micromirror_parameters
        micromirrors.apply_settings(**micromirror_parameters)
        recording_parameters['num_images'] = micromirrors.num_images
        recording_parameters['file_name'] = filename
        for tries in range(num_tries):
            print "Triggering micromirrors..."
            laser_shutters.open(color)
            micromirrors.display_pattern()
            try:
                if filename is not None:
                    #Don't bother to record the activation
                    camera.record_to_file(**recording_parameters)
                break #It worked!
            except Exception as exc:
                print "\n Recording failed"
                close(camera, micromirrors, laser_shutters, filter_wheel)
                (camera, micromirrors, laser_shutters, filter_wheel
                 ) = initialize(micromirror_parameters)
        else: #We failed a bunch of times
            raise exc
        micromirrors.readout() #Wait for the DMD to finish displaying
        laser_shutters.shut(color)

close(camera, micromirrors, laser_shutters, filter_wheel)

import numpy
all_the_data = [[], [], []]
##for i in (-1, 0, 1):
##    for j in (-1, 0, 1):
for i, j, k in (
    (4, 0, 0),
    (-4, 0, 0),
    (0, 0, 0),
    (0, 4, 0),
    (0, -4, 0),
    (4, 0, 1),
    (-4, 0, 1),
    (0, 0, 1),
    (0, 4, 1),
    (0, -4, 1)
    ):
    for n, name in enumerate((
        './nSIM/bleachdown/%i_%i_%i.raw'%(i, j, k),
        './nSIM/activation/%i_%i_%i.raw'%(i, j, k),
        './nSIM/readout/%i_%i_%i.raw'%(i, j, k),
        )):
        print name
        all_the_data[n].append(numpy.fromfile(name))
for n in range(3):
    all_the_data[n] = numpy.concatenate(all_the_data[n])
    all_the_data[n].tofile(('./nSIM/bleachdown/data.raw',
                            './nSIM/activation/data.raw',
                            './nSIM/readout/data.raw')[n])
