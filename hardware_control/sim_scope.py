import os, time, re, string
import pco, dmd, stage, shutters, wheel
import numpy

def get_save_file():
    import Tkinter, tkFileDialog
    tkroot = Tkinter.Tk()
    tkroot.withdraw()
    data_file = str(os.path.normpath(tkFileDialog.asksaveasfilename(
        title=("Choose a file name and location"),
        filetypes=[('Raw binary', '.raw')],
        defaultextension='.raw',
        initialdir='D:\\SIM_data',
        initialfile='image.raw'))) #Careful about Unicode here!
    tkroot.destroy()
    print "Data filename:", repr(data_file)
    if data_file == '.':
        raise UserWarning('No save file selected')
    save_path, file_basename = os.path.split(data_file)
    return save_path, file_basename

def max_proj_stack(
    data_filenames_list=None,
    data_filename_pattern='image_z????.raw',
    data_folder=None,
    data_dimensions=(480, 480)):
    """If data_filenames_list is given, data_filename is ignored"""

    import glob, os, sys
    import numpy

    if data_filenames_list is None:
        if data_folder is None:
            import Tkinter, tkFileDialog
            tkroot = Tkinter.Tk()
            tkroot.withdraw()
            data_folder = tkFileDialog.askdirectory(
                title=("Choose a data folder"))
            tkroot.destroy()
        data_filename_pattern = os.path.join(data_folder, data_filename_pattern)
        data_filenames_list = sorted(glob.glob(data_filename_pattern))
    elif data_folder is None: #Still need to know this, but we can guess.
        data_folder = os.path.dirname(data_filenames_list[0])

    if len(data_filenames_list) > 0:
        max_projections = numpy.zeros(
            ((len(data_filenames_list),) + data_dimensions), dtype=numpy.uint16)
        pix_per_slice = data_dimensions[0] * data_dimensions[1]
        for i, f in enumerate(data_filenames_list):
            print "Projecting:", os.path.split(f)[1]
            raw_data = numpy.fromfile(f, dtype=numpy.uint16)
            raw_data = raw_data.reshape(
                (raw_data.shape[0]/pix_per_slice,) + data_dimensions)
            max_projections[i, :, :] = raw_data.max(axis=0)

        basename = ('stack_of_max_projections_' +
                    os.path.splitext(
                        os.path.split(data_filename_pattern
                                      )[1])[0].replace('?','X'))
        max_projections.tofile(
            os.path.join(data_folder, basename + '.raw'))

        notes = open(os.path.join(
            data_folder, basename + '.txt'), 'wb')
        notes.write("Left/right: %i pixels\r\n"%(max_projections.shape[2]))
        notes.write("Up/down: %i pixels\r\n"%(max_projections.shape[1]))
        notes.write("Number of images: %i\r\n"%(max_projections.shape[0]))
        notes.write("Data type: 16-bit unsigned integers\r\n")
        notes.write("Byte order: Intel (little-endian))\r\n")
        notes.close()
    else:
        print "No files found."
    return None

def snap(
    colors=[('488', 'f3')],
    file_basename='image.raw', save_path=None, preframes=3,
    pattern='sim', repetition_period_microseconds='4500',
    illumination_microseconds=None):
    input_variables = locals()
    return z_t_series(**input_variables)
    
def z_t_series(
    colors=[('488', 'f3')], z_positions=[None], time_delays=[None],
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
        'illuminate_time': exposure['it'],
        'picture_time': exposure['pt'],
        }
    if pattern == 'sim':
        micromirror_parameters[
            'illumination_filename'] = 'illumination_pattern.raw'
    elif pattern == 'widefield':
        micromirror_parameters[
            'illumination_filename'] = 'widefield_pattern.raw'
        print "Using widefield pattern"
    else:
        raise UserWarning("'pattern' must be 'sim' or 'widefield'")
    micromirrors = dmd.Micromirror_Subprocess(**micromirror_parameters)

    laser_shutters = shutters.Laser_Shutters(colors=[c[0] for c in colors])
    shutter_delay = 0.05 #Extra seconds we wait for the shutter to open (zero?)

    filter_wheel = wheel.Filter_Wheel(initial_position=colors[0][1])
    
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
            filter_wheel.move(colors[0][1])
            laser_shutters.open(colors[0][0])
            time.sleep(shutter_delay)
        if len(time_delays) > 1:
            time_delays = [0] + time_delays
        for j, delay in enumerate(time_delays):
            if delay is not None:
                print "\nPausing for %0.3f seconds..."%(delay)
                if delay > 0:
                    for c in colors:
                        laser_shutters.shut(c[0])
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
                        filter_wheel.move(c[1])
                        laser_shutters.open(c[0])
                        time.sleep(shutter_delay)
                    file_name = (basename + '_c' + c[0] + '_' + c[1] +
                                 t_index + z_index + ext)
                    print file_name
                    for tries in range(4):
                        print "Triggering micromirrors..."
                        micromirrors.display_pattern()
                        try:
                            camera.record_to_file(
                                num_images=micromirrors.num_images, preframes=preframes,
                                file_name=file_name, save_path=save_path)
                        except Exception as exc:
                            laser_shutters.shut(c[0])
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
                            filter_wheel.move(c[1])
                            laser_shutters.open(c[0])
                            time.sleep(shutter_delay)
                        else: #It worked!
                            if len(colors) > 1:
                                laser_shutters.shut(c[0])
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
        filter_wheel.close()
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
                            ': c= %s'%(c[0]) +
                            ', f= %s'%(c[1]) +
                            ', z= %+0.3f microns'%(z*0.1) +
                            ', t= %0.4f seconds\r\n'%(t))
            index.close()
        data_filename_pattern = (
            basename + '_c???_f?' +
            re.sub('[%s]'%string.digits, '?', t_index) +
            re.sub('[%s]'%string.digits, '?', z_index) +
            ext) #Hard-coded ???? lengths...
        print "\nFilename pattern:", data_filename_pattern
        max_proj_stack(
            data_filenames_list=[os.path.join(save_path, f) for f in filenames],
            data_filename_pattern=data_filename_pattern,
            data_dimensions=(480, 480)) #Hard-coded dimensions, too...
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
##        colors=[('488', 'f3')]
##        )

##    filenames, t_points, z_points = z_t_series(
##        time_delays=[None],
####        z_positions=[0],
##        z_positions=range(-100, 100, 1),
##        repetition_period_microseconds='4500',
####        illumination_microseconds=100, #important for widefield
##        pattern='sim',
##        colors=[('488', 'f1')]
##        )

    filenames, t_points, z_points = z_t_series(
        time_delays=[0]*5,
##        z_positions=[0],
        z_positions=range(-20, 40, 2), 
        repetition_period_microseconds='4500',
##        illumination_microseconds=1200, #important for widefield
        pattern='sim',
        colors=[('488', 'f1')]
        )

    
