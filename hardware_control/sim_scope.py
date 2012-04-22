import os, time
import pco, dmd, stage, shutters
import numpy

def get_save_file():
    import Tkinter, tkFileDialog
    tkroot = Tkinter.Tk()
    tkroot.withdraw()
    data_file = str(os.path.normpath(tkFileDialog.asksaveasfilename(
        title=("Choose a file name and location"),
        filetypes=[('Raw binary', '.raw')],
        defaultextension='.raw',
        initialfile='image.raw'))) #Careful about Unicode here!
    tkroot.destroy()
    if data_file == '':
        raise UserWarning('No save file selected')
    save_path, file_basename = os.path.split(data_file)
    return save_path, file_basename

def snap(
    colors=['488'],
    file_basename='image.raw', save_path=None, preframes=3,
    pattern='sim', repetition_period_microseconds='4500',
    illumination_microseconds=None):
    input_variables = locals()
    return z_t_series(**input_variables)
    
def z_t_series(
    colors=['488'], z_positions=[None], time_delays=[None],
    file_basename=None, save_path=None, preframes=3,
    pattern='sim', repetition_period_microseconds='4500',
    illumination_microseconds=None):
    """Take a sequence of SIM or widefield frames while moving the piezo"""
    if file_basename is None or save_path is None:
        save_path, file_basename = get_save_file()

    print "Preframes to be discarded:", preframes

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

    if illumination_microseconds is not None:
        illumination_microseconds = int(illumination_microseconds)
        if exposure['it'] > illumination_microseconds:
            exposure['it'] = illumination_microseconds
        else:
            print "Max illumination time:", exposure['it'], 'microseconds.'
            print "Requested illumination time:", illumination_microseconds
            raise UserWarning('Pick a shorter exposure time')

    micromirror_parameters = {
        'delay': 0.02,
        'pattern': pattern,
        'illuminate_time': exposure['it'],
        'picture_time': exposure['pt'],
        }
    micromirrors = dmd.Micromirror_Subprocess(**micromirror_parameters)

    laser_shutters = shutters.Laser_Shutters()
    shutter_delay = 0.05 #Extra seconds we wait for the shutter to open (zero?)
    
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
    filenames, c_points, z_points, t_points = [], [], [], []
    try: #Don't worry, we re-raise exceptions in here!
        if len(colors) == 1:
            laser_shutters.open(colors[0])
            time.sleep(shutter_delay)
        if len(time_delays) > 1:
            time_delays = [0] + time_delays
        for j, delay in enumerate(time_delays):
            if delay is not None:
                print "\nPausing for %0.3f seconds..."%(delay)
                if delay > 0:
                    for c in colors:
                        laser_shutters.shut(c)
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
                for c in colors:
                    if len(colors) > 1 or delay > 0:
                        laser_shutters.open(c)
                        time.sleep(shutter_delay)
                    file_name = basename + '_c' + c + t_index + z_index + ext
                    print file_name
                    for tries in range(4):
                        print "Triggering micromirrors..."
                        micromirrors.display_pattern()
                        try:
                            camera.record_to_file(
                                num_images=micromirrors.num_images, preframes=preframes,
                                file_name=file_name, save_path=save_path)
                        except Exception as exc:
                            laser_shutters.shut(c)
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
                            laser_shutters.open(c)
                            time.sleep(shutter_delay)
                        else: #It worked!
                            if len(colors) > 1:
                                laser_shutters.shut(c)
                            break
                    else: #We failed a bunch of times
                        raise exc

                    filenames.append(file_name)
                    z_points.append(z)
                    t_points.append(time.clock())
                    c_points.append(c)
                    print "DMD subprocess report:"
                    micromirrors.readout()
    except:
        print "Something went wrong, better close the shutters..."
        raise
    finally:
        laser_shutters.close()
        camera.close()
        micromirrors.close()
        if z_positions[0] is not None:
            piezo.close()
        if z_positions[0] is not None or time_delays[0] is not None:
            index = open(os.path.join(save_path, basename + '_index.txt'), 'wb')
            for i, fn in enumerate(filenames):
                z = z_points[i]
                if z is None:
                    z = 0
                t = t_points[i]
                c = c_points[i]
                index.write(fn +
                            ': c= %s'%(c) +
                            ', z= %+0.3f microns'%(z*0.1) +
                            ', t= %0.4f seconds\r\n'%(t))
            index.close()
    return filenames, t_points, z_points

if __name__ == '__main__':

    """
    HOLY CRAP DON'T EDIT ANYHTHING ABOVE HERE

    THIS MEANS YOU, TEMPRINE!!!!!!!!!
    """
    
##    snap(
##        repetition_period_microseconds='4500',
####        illumination_microseconds=None, #Important for widefield
##        pattern='sim',
##        colors=['488']
##        )

    filenames, t_points, z_points = z_t_series(
        time_delays=[None],
        z_positions=range(-20,20,10),
        repetition_period_microseconds='4500',
##        illumination_microseconds=100, #important for widefield
        pattern='sim',
        colors=['488']
        )

    
