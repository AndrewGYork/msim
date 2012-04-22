import os, time
import pco, dmd, stage

def snap(file_basename='image.raw', save_path=None, preframes=3):
    return z_t_series(z_positions=[None], file_basename=file_basename,
          save_path=save_path, preframes=preframes)
    
def z_t_series(
    z_positions=[None], time_delays=[None],
    file_basename='image.raw', save_path=None, preframes=3):
    """Take a sequence of SIM frames while moving the piezo"""

    micromirror_delay = 0.02
    micromirrors = dmd.Micromirror_Subprocess(delay=micromirror_delay)
    print "Preframes to be discarded:", preframes

    if z_positions[0] is not None:
        piezo = stage.Z()
    camera = pco.Edge()
    trigger = "external trigger/software exposure control"
    camera.apply_settings(trigger=trigger)
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
            print "Triggering micromirrors..."
            micromirrors.display_pattern() #DMD should fire shortly after this
            try:
                camera.record_to_file(
                    num_images=micromirrors.num_images, preframes=preframes,
                    file_name=file_name, save_path=save_path)
            except:
                print "\n Recording failed"
                print "Retrying once.\n"
                print "Micromirrors postmortem:"
                micromirrors.close()
                print "Reopening micromirrors..."
                micromirrors = dmd.Micromirror_Subprocess(
                    delay=micromirror_delay)
                print "Closing and reopening camera..."
                camera.close()
                camera = pco.Edge()
                camera.apply_settings(trigger=trigger)
                camera.arm()
                print "Triggering micromirrors..."
                micromirrors.display_pattern()
                try:
                    camera.record_to_file(
                        num_images=micromirrors.num_images, preframes=preframes,
                        file_name=file_name, save_path=save_path)
                except:
                    print "Hm, a second failure. What the heck?"
                    micromirrors.close()
                    raise
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
    snap()

##    filenames, t_points, z_points = z_t_series(
##        time_delays=[None],
##        z_positions=range(-20, 20, 1),
##        file_basename='beads_488.raw')
    
##    import numpy, pylab
##    fig = pylab.figure()
##    pylab.plot(numpy.diff(t_points), '.-')
##    fig.show()
##    fig.canvas.draw()

    
