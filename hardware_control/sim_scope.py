import os, time
import pco, dmd, stage

def snap(
    file_basename='image.raw', save_path=None, preframes=3,
    pattern='sim', repetition_period_microseconds='4500'):
    input_variables = locals()
    return z_t_series(**input_variables)
    
def z_t_series(
    z_positions=[None], time_delays=[None],
    file_basename='image.raw', save_path=None, preframes=3,
    pattern='sim', repetition_period_microseconds='4500'):
    """Take a sequence of SIM or widefield frames while moving the piezo"""

    available_exposures = {
        '4500': {'pt': 4500, 'it': 2200, 'et': 2200},
        '9000': {'pt': 9000, 'it': 6800, 'et': 6700},
        '15000': {'pt': 15000, 'it': 12600, 'et': 12600},
        '25000': {'pt': 25000, 'it': 22600, 'et': 22600},
        '50000': {'pt': 50000, 'it': 47600, 'et': 47600},
        '100000': {'pt': 100000, 'it': 97500, 'et': 97500},
        }
    try:
        exposure = available_exposures[repetition_period_microseconds]
    except KeyError:
        print "Requested exposure time not recognized."
        print "Available repetition times (microseconds):"
        for k in sorted([int(k) for k in available_exposures.keys()]):
            print k
        raise

    micromirror_parameters = {
        'delay': 0.02,
        'pattern': pattern,
        'illuminate_time': exposure['it'],
        'picture_time': exposure['pt'],
        }
    micromirrors = dmd.Micromirror_Subprocess(**micromirror_parameters)
    print "Preframes to be discarded:", preframes

    if z_positions[0] is not None:
        piezo = stage.Z()
    camera = pco.Edge()
    camera_parameters = {
        'trigger': "external trigger/software exposure control",
        'exposure_time_microseconds': exposure['et'],
        }
    camera.apply_settings(**camera_parameters)
    camera.arm()
    basename, ext = os.path.splitext(file_basename)
    filenames, z_points, t_points = [], [], []
    for j, delay in enumerate(time_delays):
        if delay is not None:
            print "\nPausing for %0.3f seconds..."%(delay)
            time.sleep(delay)
            print "Done pausing."
            t_index = '_t%04i'%(j)
        else:
            t_index = ''
        for i, z in enumerate(z_positions):
            if z is not None:
                piezo.move(float(z))
                z_index = '_z%04i'%(i)
            else:
                z_index = ''
            file_name = basename + t_index + z_index + ext
            filenames.append(file_name)
            print file_name
            for tries in range(1):
                print "Triggering micromirrors..."
                micromirrors.display_pattern()
                try:
                    camera.record_to_file(
                        num_images=micromirrors.num_images, preframes=preframes,
                        file_name=file_name, save_path=save_path)
                except Exception as exc:
                    print "\n Recording failed"
                    print "Retrying...\n"
                    print "Micromirrors postmortem:"
                    micromirrors.close()
                    print "Reopening micromirrors..."
                    micromirrors = dmd.Micromirror_Subprocess(
                        **micromirror_parameters)
                    print "Closing and reopening camera..."
                    camera.close()
                    camera = pco.Edge()
                    camera.apply_settings(**camera_parameters)
                    camera.arm()
                else: #It worked!
                    break
            else: #We failed a bunch of times
                micromirrors.close()
                raise exc

            z_points.append(z)
            t_points.append(time.clock())
            print "DMD subprocess report:"
            micromirrors.readout()
    camera.close()
    micromirrors.close()
    if z_positions[0] is not None:
        piezo.close()
    if z_positions[0] is not None or time_delays[0] is not None:
        index = open(basename + '_index.txt', 'wb')
        for i, fn in enumerate(filenames):
            z = z_points[i]
            t = t_points[i]
            index.write(fn +
                        ': z= %+0.3f microns'%(z*0.1) +
                        ', t= %0.4f seconds\r\n'%(t))
        index.close()
    return filenames, t_points, z_points

if __name__ == '__main__':
    snap(repetition_period_microseconds='4500', pattern='widefield')

##    filenames, t_points, z_points = z_t_series(
##        time_delays=[None],
##        z_positions=range(0, 60, 0.5),
##        file_basename='tubules_488.raw',
##        repetition_period_microseconds='4500',
##        pattern='sim')
    
##    import numpy, pylab
##    fig = pylab.figure()
##    pylab.plot(numpy.diff(t_points), '.-')
##    fig.show()
##    fig.canvas.draw()

    
