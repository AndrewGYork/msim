import os, sys, cPickle, pprint, subprocess, time, random
from itertools import product
import numpy, pylab
from scipy.ndimage import gaussian_filter, median_filter, interpolation
from scipy.signal import hann, gaussian

def get_lattice_vectors(
    filename_list=['Sample.raw'],
    lake=None,
    bg=None,
    use_lake_lattice=False,
    use_all_lake_parameters=False,
    xPix=512,
    yPix=512,
    zPix=201,
    bg_zPix=200,
    preframes=0,
    extent=15,
    num_spikes=300,
    tolerance=3.,
    num_harmonics=3,
    outlier_phase=1.,
    calibration_window_size=10,
    scan_type='visitech',
    scan_dimensions=None,
    verbose=False,
    display=False,
    animate=False,
    show_interpolation=False,
    show_calibration_steps=False,
    show_lattice=False,
    record_parameters=True):

    if len(filename_list) < 1:
        raise UserWarning('Filename list is empty.')
    
    """Given a swept-field confocal image stack, finds
    the basis vectors of the illumination lattice pattern."""
    if lake is not None:
        print " Detecting lake illumination lattice parameters..."
        (lake_lattice_vectors, lake_shift_vector, lake_offset_vector
         ) = get_lattice_vectors(
             filename_list=[lake], lake=None, bg=None,
             xPix=xPix, yPix=yPix, zPix=zPix, preframes=preframes,
             extent=extent,
             num_spikes=num_spikes,
             tolerance=tolerance,
             num_harmonics=num_harmonics,
             outlier_phase=outlier_phase,
             scan_type=scan_type,
             scan_dimensions=scan_dimensions,
             verbose=verbose,
             display=display,
             animate=animate,
             show_interpolation=show_interpolation,
             show_lattice=show_lattice)
        print "Lake lattice vectors:"
        for v in lake_lattice_vectors:
            print v
        print "Lake shift vector:"
        pprint.pprint(lake_shift_vector)
        print "Lake initial position:"
        print lake_offset_vector
        print " Detecting sample illumination parameters..."
    if use_all_lake_parameters and (lake is not None):
        direct_lattice_vectors = lake_lattice_vectors
        shift_vector = lake_shift_vector
        corrected_shift_vector = lake_shift_vector
        offset_vector = lake_offset_vector
    elif use_lake_lattice and (lake is not None):
        """Keep the lake's lattice and crude shift vector"""
        direct_lattice_vectors = lake_lattice_vectors
        shift_vector = lake_shift_vector
        """The offset vector is now cheap to compute"""
        first_image_proj = numpy.zeros((xPix, yPix), dtype=numpy.float)
        print "Computing projection of first image..."
        for i, f in enumerate(filename_list):
            im = load_image_slice(
                filename=f, xPix=xPix, yPix=yPix, preframes=preframes,
                which_slice=0)
            first_image_proj = numpy.where(
                im > first_image_proj, im, first_image_proj)
            sys.stdout.write('\rProjecting image %i'%(i))
            sys.stdout.flush()
        print
        offset_vector = get_offset_vector(
            image=first_image_proj,
            direct_lattice_vectors=direct_lattice_vectors,
            verbose=verbose, display=display,
            show_interpolation=show_interpolation)
        """And the shift vector is cheap to correct"""
        last_image_proj = numpy.zeros((xPix, yPix), dtype=numpy.float)
        print "Computing projection of first image..."
        for f in filename_list:
            im = load_image_slice(
                filename=f, xPix=xPix, yPix=yPix, preframes=preframes,
                which_slice=zPix-1)
            last_image_proj = numpy.where(
                im > last_image_proj, im, last_image_proj)
            sys.stdout.write('\rProjecting image %i'%(i))
            sys.stdout.flush()
        print
        corrected_shift_vector, final_offset_vector = get_precise_shift_vector(
            direct_lattice_vectors, shift_vector, offset_vector,
            last_image_proj, zPix, scan_type, verbose)
    else:
        if len(filename_list) > 1:
            raise UserWarning(
                "Processing multiple files without a lake calibration" +
                " is not supported.")
        """We do this the hard way"""
        image_data = load_image_data(
            filename_list[0], xPix=xPix, yPix=yPix, zPix=zPix,
            preframes=preframes)
        fft_data_folder, fft_abs, fft_avg = get_fft_abs(
            filename_list[0], image_data) #DC term at center
        filtered_fft_abs = spike_filter(fft_abs)

        """Find candidate spikes in the Fourier domain"""
        coords = find_spikes(
            fft_abs, filtered_fft_abs, extent=extent, num_spikes=num_spikes,
            display=display, animate=animate)
        """Use these candidate spikes to determine the
        Fourier-space lattice"""
        if verbose: print "Finding Fourier-space lattice vectors..."
        basis_vectors = get_basis_vectors(
            fft_abs, coords, extent=extent, tolerance=tolerance,
            num_harmonics=num_harmonics, verbose=verbose)
        if verbose:
            print "Fourier-space lattice vectors:"
            for v in basis_vectors:
                print v, "(Magnitude", numpy.sqrt((v**2).sum()), ")"
        """Correct the Fourier-space vectors by constraining their
        sum to be zero"""
        error_vector = sum(basis_vectors)
        corrected_basis_vectors = [
            v - ((1./3.) * error_vector) for v in basis_vectors]
        if verbose:
            print "Fourier-space lattice vector triangle sum:", error_vector
            print "Corrected Fourier-space lattice vectors:"
            for v in corrected_basis_vectors:
                print v            
        """Determine the real-space lattice from the Fourier lattice"""
        area = numpy.cross(
            corrected_basis_vectors[0], corrected_basis_vectors[1])
        rotate_90 = ((0., -1.), (1., 0.))
        direct_lattice_vectors = [
            numpy.dot(v, rotate_90) * fft_abs.shape / area
            for v in corrected_basis_vectors]
        if verbose:
            print "Real-space lattice vectors:"
            for v in direct_lattice_vectors:
                print v, "(Magnitude", numpy.sqrt((v**2).sum()), ")"
            print "Lattice vector triangle sum:",
            print sum(direct_lattice_vectors)
            print "Unit cell area: (%0.2f)^2 square pixels"%(
                numpy.sqrt(numpy.abs(numpy.cross(direct_lattice_vectors[0],
                                                 direct_lattice_vectors[1]))))
        """Use the Fourier lattice and the image data to measure
        shift and offset"""
        offset_vector = get_offset_vector(
            image=image_data[0, :, :],
            direct_lattice_vectors=direct_lattice_vectors,
            verbose=verbose, display=display,
            show_interpolation=show_interpolation)

        shift_vector = get_shift_vector(
            corrected_basis_vectors, fft_data_folder, filtered_fft_abs,
            num_harmonics=num_harmonics, outlier_phase=outlier_phase,
            verbose=verbose, display=display,
            scan_type=scan_type, scan_dimensions=scan_dimensions)
        
        corrected_shift_vector, final_offset_vector = get_precise_shift_vector(
            direct_lattice_vectors, shift_vector, offset_vector,
            image_data[-1, :, :], zPix, scan_type, verbose)

    if show_lattice:
        which_filename = 0
        while True:
            print "Displaying:", filename_list[which_filename]
            image_data = load_image_data(
                filename_list[which_filename],
                xPix=xPix, yPix=yPix, zPix=zPix, preframes=preframes)
            show_lattice_overlay(
                image_data, direct_lattice_vectors,
                offset_vector, corrected_shift_vector)
            if len(filename_list) > 1:
                which_filename = raw_input(
                    "Display lattice overlay for which dataset? [done]:")
                try:
                    which_filename = int(which_filename)
                except ValueError:
                    if which_filename == '':
                        print "Done displaying lattice overlay."
                        break
                    else:
                        continue
                if which_filename >= len(filename_list):
                    which_filename = len(filename_list) - 1
            else:
                break

    #image_data is large. Figures hold references to it, stinking up the place.
    if display or show_lattice:
        pylab.close('all')
        import gc
        gc.collect() #Actually required, for once!

    if record_parameters:
        params = open(os.path.join(
            os.path.dirname(filename_list[0]), 'parameters.txt'), 'wb')
        params.write("Direct lattice vectors:" +
                     repr(direct_lattice_vectors) + "\r\n\r\n")
        params.write("Corrected shift vector:" +
                     repr(corrected_shift_vector) + "\r\n\r\n")
        params.write("Offset vector:" +
                     repr(offset_vector) + "\r\n\r\n")
        try:
            params.write("Final offset vector:" +
                         repr(final_offset_vector) + "\r\n\r\n")
        except UnboundLocalError:
            params.write("Final offset vector: Not recorded\r\n\r\n")            
        if lake is not None:
            params.write("Lake filename:" + lake + "\r\n\r\n")
        params.close()
        

    if lake is None or bg is None:
        return (direct_lattice_vectors, corrected_shift_vector, offset_vector)
    else:
        (intensities_vs_galvo_position, background_frame
         ) = spot_intensity_vs_galvo_position(
             lake, xPix, yPix, zPix, preframes,
             lake_lattice_vectors, lake_shift_vector, lake_offset_vector,
             bg, bg_zPix, window_size=calibration_window_size,
             verbose=verbose, show_steps=show_calibration_steps)
        return (direct_lattice_vectors, corrected_shift_vector, offset_vector,
                intensities_vs_galvo_position, background_frame)

def enderlein_image_parallel(
    data_filename, lake_filename, background_filename,
    xPix, yPix, zPix, steps, preframes,
    lattice_vectors, offset_vector, shift_vector,
    new_grid_xrange, new_grid_yrange,
    num_processes=1,
    window_footprint=10,
    aperture_size=3,
    make_widefield_image=True,
    make_confocal_image=False, #Broken, for now
    verbose=True,
    show_steps=False, #For debugging
    show_slices=False, #For debugging
    intermediate_data=False, #Memory hog, for stupid reasons, leave 'False'
    normalize=False, #Of uncertain merit, leave 'False' probably
    display=False,
    ):
    input_arguments = locals()
    input_arguments.pop('num_processes')

    print "\nCalculating Enderlein image"
    print

    basename = os.path.splitext(data_filename)[0]
    enderlein_image_name = basename + '_enderlein_image.raw'

    if os.path.exists(enderlein_image_name):
        print "\nEnderlein image already calculated."
        print "Loading", os.path.split(enderlein_image_name)[1]
        images = {}
        try:
            images['enderlein_image'] = numpy.fromfile(
                enderlein_image_name, dtype=float
                ).reshape(new_grid_xrange[2], new_grid_yrange[2])
        except ValueError:
            print "\n\nWARNING: the data file:"
            print enderlein_image_name
            print "may not be the size it was expected to be.\n\n"
            raise
    else:
        start_time = time.clock()
        if num_processes == 1:
            images = enderlein_image_subprocess(**input_arguments)
        else:
            input_arguments['intermediate_data'] = False #Difficult for parallel
            input_arguments['show_steps'] = False #Difficult for parallel
            input_arguments['show_slices'] = False #Difficult for parallel
            input_arguments['display'] = False #Annoying for parallel
            input_arguments['verbose'] = False #Annoying for parallel
            
            step_boundaries = range(0, steps, 10) + [steps]
            step_boundaries = [
                (step_boundaries[i], step_boundaries[i+1] - 1)
                for i in range(len(step_boundaries)-1)]
            running_processes = {}
            first_harvest = True
            random_prefix = '%06i_'%(random.randint(0, 999999))
            while len(running_processes) > 0 or len(step_boundaries) > 0:
                """Load up the subprocesses"""
                while (len(running_processes) < num_processes and
                       len(step_boundaries) > 0):
                    sb = step_boundaries.pop(0)
                    (input_arguments['start_frame'],
                     input_arguments['end_frame']) = (sb)
                    output_filename = (random_prefix +
                                       '%i_%i_intermediate_data.temp'%(sb))
                    sys.stdout.write(
                        "\rProcessing frames: " + repr(sb[0]) + '-' +
                        repr(sb[1]) + ' '*10)
                    sys.stdout.flush()
                    command_string = """
import array_illumination, cPickle
from numpy import array
input_arguments=%s
sub_images = array_illumination.enderlein_image_subprocess(**input_arguments)
cPickle.dump(sub_images, open('%s', 'wb'), protocol=2)
"""%(repr(input_arguments), output_filename)
                    running_processes[output_filename] = subprocess.Popen(
                        [sys.executable, '-c %s'%command_string],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE)
                """Poke each subprocess, harvest the finished ones"""
                pop_me = []
                for f, proc in running_processes.items():
                    if proc.poll() is not None: #Time to harvest
                        pop_me.append(f)
                        report = proc.communicate()
                        if report != ('', ''):
                            print report
                            raise UserWarning("Problem with a subprocess.")
                        sub_images = cPickle.load(open(f, 'rb'))
                        os.remove(f)
                        
                        if first_harvest:
                            images = sub_images
                            first_harvest = False
                        else:
                            for k in images.keys():
                                images[k] += sub_images[k]
                for p in pop_me: #Forget about the harvested processes
                    running_processes.pop(p)
                """Chill for a second"""
                time.sleep(0.2)
        end_time = time.clock()
        print "Elapsed time: %0.2f seconds"%(end_time - start_time)
        images['enderlein_image'].tofile(enderlein_image_name)
        if make_widefield_image:
            images['widefield_image'].tofile(basename + '_widefield.raw')
        if make_confocal_image:
            images['confocal_image'].tofile(basename + '_confocal.raw')
    if display:
        fig = pylab.figure()
        pylab.imshow(images['enderlein_image'],
                     interpolation='nearest', cmap=pylab.cm.gray)
        pylab.colorbar()
        fig.show()
    return images

def enderlein_image_subprocess(
    data_filename, lake_filename, background_filename,
    xPix, yPix, zPix, steps, preframes,
    lattice_vectors, offset_vector, shift_vector,
    new_grid_xrange, new_grid_yrange,
    start_frame=None, end_frame=None,
    window_footprint=10,
    aperture_size=3,
    make_widefield_image=True,
    make_confocal_image=False, #Broken, for now
    verbose=True,
    show_steps=False, #For debugging
    show_slices=False, #For debugging
    intermediate_data=False, #Memory hog, for stupid reasons. Leave 'False'
    normalize=False, #Of uncertain merit, leave 'False' probably
    display=False,
    ):
    basename = os.path.splitext(data_filename)[0]
    enderlein_image_name = basename + '_enderlein_image.raw'
    lake_basename = os.path.splitext(lake_filename)[0]
    lake_intensities_name = lake_basename + '_spot_intensities.pkl'
    background_basename = os.path.splitext(background_filename)[0]
    background_name = background_basename + '_background_image.raw'

    intensities_vs_galvo_position = cPickle.load(
        open(lake_intensities_name, 'rb'))
    background_directory_name = os.path.dirname(background_name)
    try:
        background_frame = numpy.fromfile(
            background_name).reshape(xPix, yPix).astype(float)
    except ValueError:
        print "\n\nWARNING: the data file:"
        print background_name
        print "may not be the size it was expected to be.\n\n"
        raise
    try:
        hot_pixels = numpy.fromfile(
            os.path.join(background_directory_name, 'hot_pixels.txt'), sep=', ')
    except:
        hot_pixels = None
        skip_hot_pix = raw_input("Hot pixel list not found. Continue? y/[n]:")
        if skip_hot_pix != 'y':
            raise
    else:
        hot_pixels = hot_pixels.reshape(2, len(hot_pixels)/2)

    if show_steps or show_slices: fig = pylab.figure()
    if start_frame is None:
        start_frame = 0
    if end_frame is None:
        end_frame = steps - 1
    new_grid_x = numpy.linspace(*new_grid_xrange)
    new_grid_y = numpy.linspace(*new_grid_yrange)
    enderlein_image = numpy.zeros(
        (new_grid_x.shape[0], new_grid_y.shape[0]), dtype=numpy.float)
    enderlein_normalization = numpy.zeros_like(enderlein_image)
    this_frames_enderlein_image = numpy.zeros_like(enderlein_image)
    this_frames_normalization = numpy.zeros_like(enderlein_image)
    if intermediate_data:
        cumulative_sum = numpy.memmap(
            basename + '_cumsum.raw', dtype=float, mode='w+',
            shape=(steps,) + enderlein_image.shape)
        processed_frames = numpy.memmap(
            basename + '_frames.raw', dtype=float, mode='w+',
            shape=(steps,) + enderlein_image.shape)
    if make_widefield_image:
        widefield_image = numpy.zeros_like(enderlein_image)
        widefield_coordinates = numpy.meshgrid(new_grid_x, new_grid_y)
        widefield_coordinates = (
            widefield_coordinates[0].reshape(
                new_grid_x.shape[0] * new_grid_y.shape[0]),
            widefield_coordinates[1].reshape(
                new_grid_x.shape[0] * new_grid_y.shape[0]))
    if make_confocal_image:
        confocal_image = numpy.zeros_like(enderlein_image)
    enderlein_normalization.fill(1e-12)
    aperture = gaussian(2*window_footprint+1, std=aperture_size
                        ).reshape(2*window_footprint+1, 1)
    aperture = aperture * aperture.T
    grid_step_x = new_grid_x[1] - new_grid_x[0]
    grid_step_y = new_grid_y[1] - new_grid_y[0]
    subgrid_footprint = numpy.floor(
        (-1 + window_footprint * 0.5 / grid_step_x,
         -1 + window_footprint * 0.5 / grid_step_y))
    subgrid = ( #Add 2*(r_0 - r_M) to this to get s_desired
        window_footprint + 2 * grid_step_x * numpy.arange(
            -subgrid_footprint[0], subgrid_footprint[0] + 1),
        window_footprint + 2 * grid_step_y * numpy.arange(
            -subgrid_footprint[1], subgrid_footprint[1] + 1))
    subgrid_points = ((2*subgrid_footprint[0] + 1) *
                      (2*subgrid_footprint[1] + 1))
    for z in range(start_frame, end_frame+1):
        im = load_image_slice(
            filename=data_filename, xPix=xPix, yPix=yPix,
            preframes=preframes, which_slice=z).astype(float)
        if hot_pixels is not None:
            im = remove_hot_pixels(im, hot_pixels)
        this_frames_enderlein_image.fill(0.)
        this_frames_normalization.fill(1e-12)
        if verbose:
            sys.stdout.write("\rProcessing raw data image %i"%(z))
            sys.stdout.flush()
        if make_widefield_image:
            widefield_image += interpolation.map_coordinates(
                im, widefield_coordinates
                ).reshape(new_grid_y.shape[0], new_grid_x.shape[0]).T
        lattice_points, i_list, j_list = (
            generate_lattice(
                image_shape=(xPix, yPix),
                lattice_vectors=lattice_vectors,
                center_pix=offset_vector + get_shift(
                    shift_vector, z),
                edge_buffer=window_footprint+1,
                return_i_j=True))
        for m, lp in enumerate(lattice_points):
            i, j = int(i_list[m]), int(j_list[m])
            """Take an image centered on each illumination point"""
            spot_image = get_centered_subimage(
                center_point=lp, window_size=window_footprint,
                image=im, background=background_frame)
            """Aperture the image with a synthetic pinhole"""
            intensity_normalization = 1.0 / (
                intensities_vs_galvo_position.get(
                    (i, j), {}).get(z, numpy.inf))
            if (intensity_normalization == 0 or
                spot_image.shape != (2*window_footprint+1,
                                     2*window_footprint+1)):
                continue #Skip to the next spot
            apertured_image = (aperture *
                               spot_image *
                               intensity_normalization)
            nearest_grid_index = numpy.round(
                    (lp - (new_grid_x[0], new_grid_y[0])) /
                    (grid_step_x, grid_step_y))
            nearest_grid_point = (
                (new_grid_x[0], new_grid_y[0]) +
                (grid_step_x, grid_step_y) * nearest_grid_index)
            new_coordinates = numpy.meshgrid(
                subgrid[0] + 2 * (nearest_grid_point[0] - lp[0]),
                subgrid[1] + 2 * (nearest_grid_point[1] - lp[1]))
            resampled_image = interpolation.map_coordinates(
                apertured_image,
                (new_coordinates[0].reshape(subgrid_points),
                 new_coordinates[1].reshape(subgrid_points))
                ).reshape(2*subgrid_footprint[1]+1,
                          2*subgrid_footprint[0]+1).T
            """Add the recentered image back to the scan grid"""
            if intensity_normalization > 0:
                this_frames_enderlein_image[
                    nearest_grid_index[0]-subgrid_footprint[0]:
                    nearest_grid_index[0]+subgrid_footprint[0]+1,
                    nearest_grid_index[1]-subgrid_footprint[1]:
                    nearest_grid_index[1]+subgrid_footprint[1]+1,
                    ] += resampled_image
                this_frames_normalization[
                    nearest_grid_index[0]-subgrid_footprint[0]:
                    nearest_grid_index[0]+subgrid_footprint[0]+1,
                    nearest_grid_index[1]-subgrid_footprint[1]:
                    nearest_grid_index[1]+subgrid_footprint[1]+1,
                    ] += 1
                if make_confocal_image: #FIXME!!!!!!!
                    confocal_image[
                        nearest_grid_index[0]-window_footprint:
                        nearest_grid_index[0]+window_footprint+1,
                        nearest_grid_index[1]-window_footprint:
                        nearest_grid_index[1]+window_footprint+1
                        ] += interpolation.shift(
                            apertured_image, shift=(lp-nearest_grid_point))
            if show_steps:
                pylab.clf()
                pylab.suptitle(
                    "Spot %i, %i in frame %i\nCentered at %0.2f, %0.2f\n"%(
                        i, j, z, lp[0], lp[1]) + (
                            "Nearest grid point: %i, %i"%(
                                nearest_grid_point[0],
                                nearest_grid_point[1])))
                pylab.subplot(1, 3, 1)
                pylab.imshow(
                    spot_image, interpolation='nearest', cmap=pylab.cm.gray)
                pylab.subplot(1, 3, 2)
                pylab.imshow(apertured_image, interpolation='nearest',
                             cmap=pylab.cm.gray)
                pylab.subplot(1, 3, 3)
                pylab.imshow(resampled_image, interpolation='nearest',
                             cmap=pylab.cm.gray)
                fig.show()
                fig.canvas.draw()
                response = raw_input('\nHit enter to continue, q to quit:')
                if response == 'q' or response == 'e' or response == 'x':
                    print "Done showing steps..."
                    show_steps = False
        enderlein_image += this_frames_enderlein_image
        enderlein_normalization += this_frames_normalization
        if not normalize:
            enderlein_normalization.fill(1)
            this_frames_normalization.fill(1)
        if intermediate_data:
            cumulative_sum[z, :, :] = (
                enderlein_image * 1. / enderlein_normalization)
            cumulative_sum.flush()
            processed_frames[
                z, :, :] = this_frames_enderlein_image * 1. / (
                    this_frames_normalization)
            processed_frames.flush()
        if show_slices:
            pylab.clf()
            pylab.imshow(enderlein_image * 1.0 / enderlein_normalization,
                         cmap=pylab.cm.gray, interpolation='nearest')
            fig.show()
            fig.canvas.draw()
            response=raw_input('Hit enter to continue...')

    images = {}
    images['enderlein_image'] = (
        enderlein_image * 1.0 / enderlein_normalization)
    if make_widefield_image:
        images['widefield_image'] = widefield_image
    if make_confocal_image:
        images['confocal_image'] = confocal_image
    return images

##def load_image_data(filename, xPix=512, yPix=512, zPix=201):
##    """Load the 16-bit raw data from the Visitech Infinity"""
##    return numpy.memmap(
##        filename, dtype=numpy.uint16, mode='r'
##        ).reshape(zPix, xPix, yPix) #FIRST dimension is image number

def load_image_data(filename, xPix=512, yPix=512, zPix=201, preframes=0):
    """Load the 16-bit raw data from the Visitech Infinity"""
    return numpy.memmap(#FIRST dimension is image number
        filename, dtype=numpy.uint16, mode='r'
        ).reshape(zPix+preframes, xPix, yPix)[preframes:, :, :]

def load_image_slice(filename, xPix, yPix, preframes=0, which_slice=0):
    """Load a frame of the 16-bit raw data from the Visitech Infinity"""
    bytes_per_pixel = 2
    data_file = open(filename, 'rb')
    data_file.seek((which_slice + preframes) * xPix*yPix*bytes_per_pixel)
    try:
        return numpy.fromfile(
            data_file, dtype=numpy.uint16, count=xPix*yPix
            ).reshape(xPix, yPix)
    except ValueError:
        print "\n\nWARNING: the data file:"
        print data_file
        print "may not be the size it was expected to be.\n\n"
        raise

def load_fft_slice(fft_data_folder, xPix, yPix, which_slice=0):
    bytes_per_pixel = 16
    filename = os.path.join(fft_data_folder, '%06i.dat'%(which_slice))
    data_file = open(filename, 'rb')
    return numpy.memmap(data_file, dtype=numpy.complex128, mode='r'
                        ).reshape(xPix, yPix)

def get_fft_abs(filename, image_data, show_steps=False):
    basename = os.path.splitext(filename)[0]
    fft_abs_name = basename + '_fft_abs.npy'
    fft_avg_name = basename + '_fft_avg.npy'
    fft_data_folder = basename + '_fft_data'
    """FFT data is stored as a sequence of raw binary files, one per
    2D z-slice. The files are named 000000.dat, 000001.dat, etc."""
    
    if (os.path.exists(fft_abs_name) and
        os.path.exists(fft_avg_name) and
        os.path.exists(fft_data_folder)):
        print "Loading", os.path.split(fft_abs_name)[1]
        fft_abs = numpy.load(fft_abs_name)
        print "Loading", os.path.split(fft_avg_name)[1]
        fft_avg = numpy.load(fft_avg_name)
    else:
        print "Generating fft_abs, fft_avg and fft_data..."
        os.mkdir(fft_data_folder)
        fft_abs = numpy.zeros(image_data.shape[1:])
        fft_avg = numpy.zeros(image_data.shape[1:], dtype=numpy.complex128)
        window = (hann(image_data.shape[1]).reshape(image_data.shape[1], 1) *
                  hann(image_data.shape[2]).reshape(1, image_data.shape[2]))
        if show_steps: fig = pylab.figure()
        for z in range(image_data.shape[0]):
            fft_data = numpy.fft.fftshift(#Stored shifted!
                numpy.fft.fftn(window * image_data[z, :, :], axes=(0, 1)))
            fft_data.tofile(os.path.join(fft_data_folder, '%06i.dat'%(z)))
            fft_abs += numpy.abs(fft_data)
            if show_steps:
                pylab.clf()
                pylab.subplot(1, 3, 1)
                pylab.title('Windowed slice %i'%(z))
                pylab.imshow(window * numpy.array(image_data[z, :, :]),
                             cmap=pylab.cm.gray, interpolation='nearest')
                pylab.subplot(1, 3, 2)
                pylab.title('FFT of slice %i'%(z))
                pylab.imshow(numpy.log(1 + numpy.abs(fft_data)),
                             cmap=pylab.cm.gray, interpolation='nearest')
                pylab.subplot(1, 3, 3)
                pylab.title("Cumulative sum of FFT absolute values")
                pylab.imshow(numpy.log(1 + fft_abs),
                             cmap=pylab.cm.gray, interpolation='nearest')
                fig.show()
                fig.canvas.draw()
                raw_input("Hit enter to continue...")
            fft_avg += fft_data
            sys.stdout.write('\rFourier transforming slice %i'%(z+1))
            sys.stdout.flush()
        fft_avg = numpy.abs(fft_avg)
        numpy.save(fft_abs_name, fft_abs)
        numpy.save(fft_avg_name, fft_avg)
        print
    return (fft_data_folder, fft_abs, fft_avg)

def spike_filter(fft_abs, display=False):
    f = gaussian_filter(numpy.log(1 + fft_abs), sigma=0.5)
    if display:
        fig = pylab.figure()
        pylab.imshow(f, cmap=pylab.cm.gray, interpolation='nearest')
        pylab.title('Smoothed')
        fig.show()
        fig.canvas.draw()
        raw_input('Hit enter...')
        pylab.clf()
    f = f - gaussian_filter(f, sigma=(0, 4))
    if display:
        pylab.imshow(f, cmap=pylab.cm.gray, interpolation='nearest')
        pylab.title('Filtered left-right')
        fig.show()
        fig.canvas.draw()
        raw_input('Hit enter...')
        pylab.clf()
    f = f - gaussian_filter(f, sigma=(4, 0))
    if display:
        pylab.imshow(f, cmap=pylab.cm.gray, interpolation='nearest')
        pylab.title('Filtered up-down')
        fig.show()
        fig.canvas.draw()
        raw_input('Hit enter...')
        pylab.clf()
    f = gaussian_filter(f, sigma=(1.5))
    if display:
        pylab.imshow(f, cmap=pylab.cm.gray, interpolation='nearest')
        pylab.title('Resmoothed')
        fig.show()
        fig.canvas.draw()
        raw_input('Hit enter...')
        pylab.clf()
    f = f * (f > 0)
    if display:
        pylab.imshow(f, cmap=pylab.cm.gray, interpolation='nearest')
        pylab.title('Negative truncated')
        fig.show()
        fig.canvas.draw()
        raw_input('Hit enter...')
        pylab.clf()
    f -= f.mean()
    f *= 1.0 / f.std()
    return f

def find_spikes(fft_abs, filtered_fft_abs, extent=15, num_spikes=300,
                display=True, animate=False):
    """Finds spikes in the sum of the 2D ffts of an image stack"""
    center_pix = numpy.array(fft_abs.shape)//2
    log_fft_abs = numpy.log(1 + fft_abs)
    filtered_fft_abs = numpy.array(filtered_fft_abs)

    if display:
        image_extent=[-0.5 - center_pix[1],
                     filtered_fft_abs.shape[1] - 0.5 - center_pix[1],
                     filtered_fft_abs.shape[0] - 0.5 - center_pix[0],
                     -0.5 - center_pix[0]]
        fig = pylab.figure()
        pylab.subplot(1, 2, 1)
        pylab.imshow(log_fft_abs, cmap=pylab.cm.gray,
                     interpolation='nearest', extent=image_extent)
        pylab.title('Average Fourier magnitude')
        pylab.subplot(1, 2, 2)
        pylab.imshow(numpy.array(filtered_fft_abs), cmap=pylab.cm.gray,
                     interpolation='nearest', extent=image_extent)
        pylab.title('Filtered average Fourier magnitude')
        fig.show()

    coords = []
    if animate:
        fig = pylab.figure()
        print 'Center pixel:', center_pix
    for i in range(num_spikes):
        coords.append(
            numpy.array(numpy.unravel_index(
                filtered_fft_abs.argmax(), filtered_fft_abs.shape)))
        c = coords[-1]
        xSl = slice(max(c[0]-extent, 0),
                    min(c[0]+extent, filtered_fft_abs.shape[0]))
        ySl = slice(max(c[1]-extent, 0),
                    min(c[1]+extent, filtered_fft_abs.shape[1]))
        filtered_fft_abs[xSl, ySl] = 0
        if animate:
            print i, ':', c
            pylab.clf()
            pylab.subplot(1, 2, 1)
            pylab.imshow(
                filtered_fft_abs, cmap=pylab.cm.gray, interpolation='nearest')
            pylab.colorbar()
            pylab.subplot(1, 2, 2)
            pylab.plot(filtered_fft_abs.max(axis=1))
            fig.show()
            fig.canvas.draw()
            if i == 0:
                raw_input('.')

    coords = [c - center_pix for c in coords]
    coords = sorted(coords, key=lambda x: x[0]**2 + x[1]**2)

    return coords #Lattice k-vectors, sorted by vector magnitude

def get_basis_vectors(
    fft_abs, coords, extent=15, tolerance=3., num_harmonics=3, verbose=False):
    for i in range(len(coords)): #Where to start looking.
        basis_vectors = []
        precise_basis_vectors = []
        for c, coord in enumerate(coords):
            if c < i:
                continue

            if c == 0:
                if max(abs(coord)) > 0:
                    print "c:", c
                    print "Coord:", coord
                    print "Coordinates:"
                    for x in coords: print x
                    raise UserWarning('No peak at the central pixel')
                else:
                    continue #Don't look for harmonics of the DC term

            if coord[0] < 0 or (coord[0] == 0 and coord[1] < 0):
                #Ignore the negative versions
                if verbose: print "\nIgnoring:", coord
            else:
                #Check for harmonics
                if verbose: print "\nTesting:", coord
                num_vectors, points_found = test_basis(
                    coords, [coord], tolerance=tolerance, verbose=verbose)
                if num_vectors > num_harmonics:
                    #We found enough harmonics. Keep it, for now.
                    basis_vectors.append(coord)
                    center_pix = numpy.array(fft_abs.shape)//2
                    furthest_spike = points_found[-1] + center_pix
                    if verbose:
                        print "Appending", coord
                        print "%i harmonics found, at:"%(num_vectors-1)
                        for p in points_found:
                            print ' ', p

                    if len(basis_vectors) > 1:
                        if verbose:
                            print "\nTesting combinations:", basis_vectors
                        num_vectors, points_found = test_basis(
                            coords, basis_vectors, tolerance=tolerance,
                            verbose=verbose)
                        if num_vectors > num_harmonics:
                            #The combination predicts the lattice
                            if len(basis_vectors) == 3:
                                #We're done; we have three consistent vectors.
                                precise_basis_vectors = get_precise_basis(
                                    coords, basis_vectors, fft_abs,
                                    tolerance=tolerance, verbose=verbose)
                                (x_1, x_2, x_3) = sorted(
                                    precise_basis_vectors,
                                    key=lambda x: abs(x[0]))
                                possibilities = sorted(
                                    ([x_1, x_2, x_3],
                                     [x_1, x_2, -x_3],
                                     [x_1, -x_2, x_3],
                                     [x_1, -x_2, -x_3]),
                                    key=lambda x:(numpy.array(sum(x))**2).sum())
                                if verbose:
                                    print "Possible triangle combinations:"
                                    for p in possibilities: print " ", p
                                precise_basis_vectors = possibilities[0]
                                if precise_basis_vectors[-1][0] < 0:
                                    for p in range(3):
                                        precise_basis_vectors[p] *= -1
                                return precise_basis_vectors
                        else:
                            #Blame the new guy, for now.
                            basis_vectors.pop()
    else:
        raise UserWarning(
            "Basis vector search failed. Diagnose by running with verbose=True")

def test_basis(coords, basis_vectors, tolerance, verbose=False):
    #Checks for expected lattice, returns the points found and halts on failure.
    points_found = list(basis_vectors)
    num_vectors = 2
    searching = True
    while searching:
        if verbose: print "Looking for combinations of %i basis vectors."%(
            num_vectors)
        lattice = [sum(c) for c in
                 combinations_with_replacement(basis_vectors, num_vectors)]
        if verbose: print "Expected lattice points:", lattice
        for i, lat in enumerate(lattice):
            for c in coords:
                dif = numpy.sqrt(((lat - c)**2).sum())
                if dif < tolerance:
                    if verbose:
                        print "Found lattice point:", c
                        print " Distance:", dif
                        if len(basis_vectors) == 1:
                            print " Fundamental:", c * 1.0 / num_vectors
                    points_found.append(c)
                    break
            else: #Fell through the loop
                if verbose: print "Expected lattice point not found"
                searching = False
        if not searching: return (num_vectors, points_found)
        num_vectors += 1

def get_precise_basis(coords, basis_vectors, fft_abs, tolerance, verbose=False):
    #Uses the expected lattice to estimate precise values of the basis.
    if verbose: print "\nAdjusting basis vectors to match lattice..."
    center_pix = numpy.array(fft_abs.shape) // 2
    basis_vectors = list(basis_vectors)
    spike_indices = []
    spike_locations = []
    num_vectors = 2
    searching = True
    while searching:
        """I seem to be relying on combinations_with_replacemnet to
        give the same ordering twice in a row. Hope it always does!"""
        combinations = [
            c for c in combinations_with_replacement(basis_vectors,
                                                     num_vectors)]
        combination_indices = [
            c for c in combinations_with_replacement((0, 1, 2), num_vectors)]
        for i, comb in enumerate(combinations):
            lat = sum(comb)
            key = tuple([combination_indices[i].count(v) for v in (0, 1, 2)])
            for c in coords:
                dif = numpy.sqrt(((lat - c)**2).sum())
                if dif < tolerance:
                    p = c + center_pix
                    true_max = c + simple_max_finder(
                        fft_abs[p[0] - 1:p[0] + 2,
                                p[1] - 1:p[1] + 2], show_plots=False)
                    if verbose:
                        print "Found lattice point:", c
                        print "Estimated position:", true_max
                        print "Lattice index:", key
                    spike_indices.append(key)
                    spike_locations.append(true_max)
                    break
            else: #Fell through the loop
                if verbose: print "Expected lattice point not found"
                searching = False
        if not searching: #Given the spikes found, estimate the basis
            A = numpy.array(spike_indices)
            v = numpy.array(spike_locations)
            precise_basis_vectors, residues, rank, s = numpy.linalg.lstsq(A, v)
            if verbose:
                print "Precise basis vectors:"
                print precise_basis_vectors
                print "Residues:", residues
                print "Rank:", rank
                print "s:", s
                print
            return precise_basis_vectors            
        num_vectors += 1

def combinations_with_replacement(iterable, r):
    """
    >>>print([i for i in combinations_with_replacement(['a', 'b', 'c'], 2)])
    [('a', 'a'), ('a', 'b'), ('a', 'c'), ('b', 'b'), ('b', 'c'), ('c', 'c')]
    """
    pool = tuple(iterable)
    n = len(pool)
    for indices in product(range(n), repeat=r):
        if sorted(indices) == list(indices):
            yield tuple(pool[i] for i in indices)

def get_offset_vector(
    image, direct_lattice_vectors, prefilter='median',
    verbose=True, display=True, show_interpolation=True):
    if prefilter == 'median':
        image = median_filter(image, size=3)
    if verbose: print "\nCalculating offset vector..."
    ws = 2 + int(max(
        [abs(v).max() for v in direct_lattice_vectors]))
    if verbose: print "Window size:", ws
    window = numpy.zeros([2*ws + 1]*2, dtype=numpy.float)
    lattice_points = generate_lattice(
        image.shape, direct_lattice_vectors, edge_buffer=2+ws)
    for lp in lattice_points:
        window += get_centered_subimage(
            center_point=lp, window_size=ws, image=image.astype(float))

    if display:
        fig = pylab.figure()
        pylab.imshow(window, interpolation='nearest', cmap=pylab.cm.gray)
        pylab.title('Lattice average\nThis should look like round blobs')
        fig.show()
    buffered_window = numpy.array(window)
    buffered_window[:2, :] = 0
    buffered_window[-2:, :] = 0
    buffered_window[:, :2] = 0
    buffered_window[:, -2:] = 0
    while True: #Don't want maxima on the edges
        max_pix = numpy.unravel_index(buffered_window.argmax(), window.shape)
        if ((3 < max_pix[0] < window.shape[0] - 3) and
            (3 < max_pix[1] < window.shape[1] - 3)):
            break
        else:
            buffered_window = gaussian_filter(buffered_window, sigma=2)
    if verbose: print "Maximum pixel in lattice average:", max_pix
    correction = simple_max_finder(
        window[max_pix[0]-1:max_pix[0]+2, max_pix[1]-1:max_pix[1]+2],
        show_plots=show_interpolation)
    offset_vector = max_pix + correction + numpy.array(image.shape)//2 - ws
    if verbose: print "Offset vector:", offset_vector
    return offset_vector

def simple_max_finder(a, show_plots=True):
    """Given a 3x3 array with the maximum pixel in the center,
    estimates the x/y position of the true maximum"""
    true_max = []
    interpPoints = numpy.arange(-1, 2)
    for data in (a[:, 1], a[1, :]):
        myFit = numpy.poly1d(numpy.polyfit(
            interpPoints, data, deg = 2))
        true_max.append(-myFit[1]/(2.0*myFit[2]))
    true_max = numpy.array(true_max)
    if show_plots:
        print "Correction:", true_max
        fig = pylab.figure()
        pylab.subplot(1, 3, 1)
        pylab.imshow(a, interpolation='nearest', cmap=pylab.cm.gray)
        pylab.axhline(y=1 + true_max[0])
        pylab.axvline(x=1 + true_max[1])
        pylab.subplot(1, 3, 2)
        pylab.plot(a[:, 1])
        pylab.axvline(x=1 + true_max[0])
        pylab.subplot(1, 3, 3)
        pylab.plot(a[1, :])
        pylab.axvline(x=1 + true_max[1])
        fig.show()

    return true_max

def get_shift_vector(
    fourier_lattice_vectors, fft_data_folder, filtered_fft_abs,
    num_harmonics=3, outlier_phase=1.,
    verbose=True, display=True, scan_type='visitech', scan_dimensions=None):
    if verbose: print "\nCalculating shift vector..."
    center_pix = numpy.array(filtered_fft_abs.shape) // 2
    harmonic_pixels = []
    values = {}
    for v in fourier_lattice_vectors:
        harmonic_pixels.append([])
        for i in range(1, num_harmonics+1):
            expected_pix = (numpy.round((i * v)) + center_pix).astype(int)
            roi = filtered_fft_abs[expected_pix[0] - 1:expected_pix[0] + 2,
                                   expected_pix[1] - 1:expected_pix[1] + 2]
            shift = -1 + numpy.array(
                numpy.unravel_index(roi.argmax(), roi.shape))
            actual_pix = expected_pix + shift - center_pix 
            if verbose:
                print "Expected pixel:", expected_pix - center_pix
                print "Shift:", shift
                print "Brightest neighboring pixel:", actual_pix
            harmonic_pixels[-1].append(tuple(actual_pix))
            values[harmonic_pixels[-1][-1]] = []
    num_slices = len(os.listdir(fft_data_folder))
    if verbose: print '\n'
    for z in range(num_slices):
        if verbose:
            sys.stdout.write("\rLoading harmonic pixels from FFT slice %06i"%(z))
            sys.stdout.flush()
        fft_data = load_fft_slice(
            fft_data_folder,
            xPix=filtered_fft_abs.shape[0],
            yPix=filtered_fft_abs.shape[1],
            which_slice=z)
        for hp in harmonic_pixels:
            for p in hp:
                values[p].append(
                    fft_data[p[0] + center_pix[0], p[1] + center_pix[1]])
    if verbose: print
    slopes = []
    K = []
    if display: fig = pylab.figure()
    if scan_dimensions is not None:
        scan_dimensions = tuple(reversed(scan_dimensions))
    for hp in harmonic_pixels:
        for n, p in enumerate(hp):
            values[p] = numpy.unwrap(numpy.angle(values[p]))
            if scan_type == 'visitech':
                slope = numpy.polyfit(
                    range(len(values[p])), values[p], deg=1)[0]
                values[p] -= slope * numpy.arange(len(values[p]))
            elif scan_type == 'dmd':
                if scan_dimensions[0] * scan_dimensions[1] != num_slices:
                    raise UserWarning(
                        "The scan dimensions are %i by %i," +
                        " but there are %i slices"%(
                            scan_dimensions[0], scan_dimensions[1], num_slices))
                slope = [0, 0]
                slope[0] = numpy.polyfit(
                    range(scan_dimensions[1]),
                    values[p].reshape(
                        scan_dimensions).sum(axis=0) * 1.0 / scan_dimensions[0],
                    deg=1)[0]
                values[p] -= slope[0] * numpy.arange(len(values[p]))
                slope[1] = numpy.polyfit(
                    scan_dimensions[1]*numpy.arange(scan_dimensions[0]),
                    values[p].reshape(
                        scan_dimensions).sum(axis=1) * 1.0 / scan_dimensions[1],
                    deg=1)[0]
                values[p] -= slope[1] * scan_dimensions[1] * (
                    numpy.arange(len(values[p])) // scan_dimensions[1])
                slope[1] *= scan_dimensions[1]
            values[p] -= values[p].mean()
            if abs(values[p]).mean() < outlier_phase:
                K.append(p * (-2. * numpy.pi / numpy.array(fft_data.shape)))
                slopes.append(slope)
            else:
                if verbose: print "Ignoring outlier:", p
            if display: pylab.plot(values[p],'.-', label=repr(p))
    if display:
        pylab.title('This should look like noise. Sudden jumps mean bad data!')
        pylab.ylabel('Deviation from expected phase')
        pylab.xlabel('Image number')
        pylab.grid()
        pylab.legend(prop={'size':8})
        pylab.axis('tight')
        x_limits = 1.05 * numpy.array(pylab.xlim())
        x_limits -= x_limits[-1] * 0.025
        pylab.xlim(x_limits)
        fig.show()

    if scan_type == 'visitech':
        x_s, residues, rank, s = numpy.linalg.lstsq(
            numpy.array(K), numpy.array(slopes))
    elif scan_type == 'dmd':
        x_s, residues, rank, s = {}, [0, 0], [0, 0], [0, 0]
        x_s['fast_axis'], residues[0], rank[0], s[0] = numpy.linalg.lstsq(
            numpy.array(K), numpy.array([sl[0] for sl in slopes]))
        x_s['slow_axis'], residues[1], rank[1], s[1] = numpy.linalg.lstsq(
            numpy.array(K), numpy.array([sl[1] for sl in slopes]))
        x_s['scan_dimensions'] = tuple(reversed(scan_dimensions))
    if verbose:
        print "Shift vector:"
        pprint.pprint(x_s)
        print "Residues:", residues
        print "Rank:", rank
        print "s:", s
    return x_s

def get_precise_shift_vector(
    direct_lattice_vectors, shift_vector, offset_vector,
    last_image, zPix, scan_type, verbose):
    """Use the offset vector to correct the shift vector"""
    final_offset_vector = get_offset_vector(
        image=last_image,
        direct_lattice_vectors=direct_lattice_vectors,
        verbose=False, display=False, show_interpolation=False)
    final_lattice = generate_lattice(
        last_image.shape, direct_lattice_vectors,
        center_pix=offset_vector + get_shift(
            shift_vector, zPix - 1))
    closest_approach = 1e12
    for p in final_lattice:
        dif = p - final_offset_vector
        distance_sq = (dif**2).sum()
        if distance_sq < closest_approach:
            closest_lattice_point = p
            closest_approach = distance_sq
    shift_error = closest_lattice_point - final_offset_vector
    if scan_type == 'visitech':
        movements = zPix - 1
        corrected_shift_vector = shift_vector - (shift_error * 1.0 / movements)
    elif scan_type == 'dmd':
        movements = (
            (zPix - 1) // shift_vector['scan_dimensions'][0])
        corrected_shift_vector = dict(shift_vector)
        corrected_shift_vector['slow_axis'] = (
            shift_vector['slow_axis'] - shift_error * 1.0 / movements)

    if verbose:
        print "\nCorrecting shift vector..."
        print " Initial shift vector:"
        print ' ',
        pprint.pprint(shift_vector)
        print " Final offset vector:", final_offset_vector
        print " Closest predicted lattice point:", closest_lattice_point
        print " Error:", shift_error, "in", movements, "movements"
        print " Corrected shift vector:"
        print ' ',
        pprint.pprint(corrected_shift_vector)
        print
    return corrected_shift_vector, final_offset_vector

def get_shift(shift_vector, frame_number):
    if isinstance(shift_vector, dict):
        """This means we have a 2D shift vector"""
        fast_steps = frame_number % shift_vector['scan_dimensions'][0]
        slow_steps = frame_number // shift_vector['scan_dimensions'][0]
        return (shift_vector['fast_axis'] * fast_steps +
                shift_vector['slow_axis'] * slow_steps)
    else:
        """This means we have a 1D shift vector, like the Visitech Infinity"""
        return frame_number * shift_vector

def show_lattice_overlay(
    image_data, direct_lattice_vectors, offset_vector, shift_vector):
    fig = pylab.figure()
    s = 0
    while True:
        pylab.clf()
        showMe = median_filter(numpy.array(image_data[s, :, :]), size=3)
        dots = numpy.zeros(list(showMe.shape) + [4])
        lattice_points = generate_lattice(
            showMe.shape, direct_lattice_vectors,
            center_pix=offset_vector + get_shift(shift_vector, s))
        for lp in lattice_points:
            x, y = numpy.round(lp).astype(int)
            dots[x, y, 0::3] = 1
        pylab.imshow(showMe, cmap=pylab.cm.gray, interpolation='nearest')
        pylab.imshow(dots, interpolation='nearest')
        pylab.title("Red dots show the calculated illumination pattern")
        fig.show()
        fig.canvas.draw()
        new_s = raw_input("Next frame [exit]:")
        if new_s == '':
            print "Exiting"
            break
        try:
            s = int(new_s)
        except ValueError:
            print "Response not understood. Exiting display."
            break
        s %= image_data.shape[0]
        print "Displaying frame %i"%(s)
    return None

def show_illuminated_points(
    direct_lattice_vectors, shift_vector, offset_vector='image',
    xPix=120, yPix=120, step_size=1, num_steps=200, verbose=True):
    if verbose: print "\nShowing a portion of the illumination points..."
    spots = sum(combine_lattices(
        direct_lattice_vectors, shift_vector, offset_vector,
        xPix, yPix, step_size, num_steps, verbose=verbose), [])
    fig=pylab.figure()
    pylab.plot([p[1] for p in spots], [p[0] for p in spots], '.')
    pylab.xticks(range(yPix))
    pylab.yticks(range(xPix))
    pylab.grid()
    pylab.axis('equal')
    fig.show()
    fig.canvas.draw()
    return fig

def combine_lattices(
    direct_lattice_vectors, shift_vector, offset_vector='image',
    xPix=120, yPix=120, step_size=1, num_steps=200, edge_buffer=2,
    verbose=True):
    if verbose: print "Combining lattices..."
    if offset_vector == 'image':
        offset_vector = numpy.array((xPix//2, yPix//2))
    spots = []
    for i in range(num_steps):
        spots.append([])
        if verbose:
            sys.stdout.write('\rz: %04i'%(i+1))
            sys.stdout.flush()
        spots[-1] += generate_lattice(
            image_shape=(xPix, yPix),
            lattice_vectors=direct_lattice_vectors,
            center_pix=offset_vector + get_shift(shift_vector, i*step_size),
            edge_buffer=edge_buffer)
    if verbose: print
    return spots

def spot_intensity_vs_galvo_position(
    lake_filename, xPix, yPix, zPix, preframes,
    direct_lattice_vectors, shift_vector, offset_vector,
    background_filename, background_zPix,
    window_size=5, verbose=False, show_steps=False, display=False):
    """Calibrate how the intensity of each spot varies with galvo
    position, using a fluorescent lake dataset and a stack of
    light-free background images."""

    lake_basename = os.path.splitext(lake_filename)[0]
    lake_intensities_name = lake_basename + '_spot_intensities.pkl'
    background_basename = os.path.splitext(background_filename)[0]
    background_name = background_basename + '_background_image.raw'
    background_directory_name = os.path.dirname(background_basename)
    try:
        hot_pixels = numpy.fromfile(
            os.path.join(background_directory_name, 'hot_pixels.txt'), sep=', ')
    except IOError:
        skip_hot_pix = raw_input("Hot pixel list not found. Continue? y/[n]:")
        if skip_hot_pix != 'y':
            raise
        else:
            hot_pixels = None
    else:
        hot_pixels = hot_pixels.reshape(2, len(hot_pixels)/2)
    
    if (os.path.exists(lake_intensities_name) and
        os.path.exists(background_name)):
        print "\nIllumination intensity calibration already calculated."
        print "Loading", os.path.split(lake_intensities_name)[1]
        intensities_vs_galvo_position = cPickle.load(
            open(lake_intensities_name, 'rb'))
        print "Loading", os.path.split(background_name)[1]
        try:
            bg = numpy.fromfile(background_name, dtype=float
                                ).reshape(xPix, yPix)
        except ValueError:
            print "\n\nWARNING: the data file:"
            print background_name
            print "may not be the size it was expected to be.\n\n"
            raise
    else:
        print "\nCalculating illumination spot intensities..."
        print "Constructing background image..."
        background_image_data = load_image_data(
            background_filename, xPix, yPix, background_zPix, preframes)
        bg = numpy.zeros((xPix, yPix), dtype=float)
        for z in range(background_image_data.shape[0]):
            bg += background_image_data[z, :, :]
        bg *= 1.0 / background_image_data.shape[0]
        del background_image_data
        if hot_pixels is not None:
            bg = remove_hot_pixels(bg, hot_pixels)
        print "Background image complete."

        lake_image_data = load_image_data(
            lake_filename, xPix, yPix, zPix, preframes)
        intensities_vs_galvo_position = {}
        """A dict of dicts. Element [i, j][z] gives the intensity of the
        i'th, j'th spot in the lattice, in frame z"""
        if show_steps: fig = pylab.figure()
        print "Computing flat-field calibration..."
        for z in range(lake_image_data.shape[0]):
            im = numpy.array(lake_image_data[z, :, :], dtype=float)
            if hot_pixels is not None:
                im = remove_hot_pixels(im, hot_pixels)
            sys.stdout.write("\rCalibration image %i"%(z))
            sys.stdout.flush()
            lattice_points, i_list, j_list = generate_lattice(
                image_shape=(xPix, yPix),
                lattice_vectors=direct_lattice_vectors,
                center_pix=offset_vector + get_shift(shift_vector, z),
                edge_buffer=window_size+1,
                return_i_j=True)
            
            for m, lp in enumerate(lattice_points):
                i, j = int(i_list[m]), int(j_list[m])
                intensity_history = intensities_vs_galvo_position.setdefault(
                    (i, j), {}) #Get this spot's history
                spot_image = get_centered_subimage(
                    center_point=lp, window_size=window_size,
                    image=im, background=bg)
                intensity_history[z] = float(spot_image.sum()) #Funny thing...
                if show_steps:
                    pylab.clf()
                    pylab.imshow(
                        spot_image, interpolation='nearest', cmap=pylab.cm.gray)
                    pylab.title(
                        "Spot %i, %i in frame %i\nCentered at %0.2f, %0.2f"%(
                            i, j, z, lp[0], lp[1]))
                    fig.show()
                    fig.canvas.draw()
                    response = raw_input()
                    if response == 'q' or response == 'e' or response == 'x':
                        print "Done showing steps..."
                        show_steps = False
        """Normalize the intensity values"""
        num_entries = 0
        total_sum = 0
        for hist in intensities_vs_galvo_position.values():
            for intensity in hist.values():
                num_entries += 1
                total_sum += intensity
        inverse_avg = num_entries * 1.0 / total_sum
        for hist in intensities_vs_galvo_position.values():
            for k in hist.keys():
                hist[k] *= inverse_avg
        print "\nSaving", os.path.split(lake_intensities_name)[1]
        cPickle.dump(intensities_vs_galvo_position,
                     open(lake_intensities_name, 'wb'), protocol=2)
        print "Saving", os.path.split(background_name)[1]
        bg.tofile(background_name)
    if display:
        fig=pylab.figure()
        num_lines = 0
        for (i, j), spot_hist in intensities_vs_galvo_position.items()[:10]:
            num_lines += 1
            sh = spot_hist.items()
            pylab.plot([frame_num for frame_num, junk in sh],
                       [intensity for junk, intensity in sh],
                       ('-', '-.')[num_lines > 5],
                       label=repr((i, j)))
        pylab.legend()
        fig.show()
    return intensities_vs_galvo_position, bg #bg is short for 'background'

def remove_hot_pixels(image, hot_pixels):
    for y, x in hot_pixels:
        image[x, y] = numpy.median(image[x-1:x+2, y-1:y+2])
    return image

def generate_lattice(
    image_shape, lattice_vectors, center_pix='image', edge_buffer=2,
    return_i_j=False):

    if center_pix == 'image':
        center_pix = numpy.array(image_shape) // 2
    else: ##Shift the center pixel by lattice vectors to the middle of the image
        center_pix = numpy.array(center_pix) - (numpy.array(image_shape) // 2)
        lattice_components = numpy.linalg.solve(
            numpy.vstack(lattice_vectors[:2]).T,
            center_pix)
        lattice_components_centered = numpy.mod(lattice_components, 1)
        lattice_shift = lattice_components - lattice_components_centered
        center_pix = (lattice_vectors[0] * lattice_components_centered[0] +
                      lattice_vectors[1] * lattice_components_centered[1] +
                      numpy.array(image_shape) // 2)

    num_vectors = int(numpy.round(#Hopefully an overestimate
        1.5 * max(image_shape) / numpy.sqrt(lattice_vectors[0]**2).sum()))
    lower_bounds = (edge_buffer, edge_buffer)
    upper_bounds = (image_shape[0] - edge_buffer, image_shape[1] - edge_buffer)
    i, j = numpy.mgrid[-num_vectors:num_vectors, -num_vectors:num_vectors]
    i = i.reshape(i.size, 1)
    j = j.reshape(j.size, 1)
    lp = i*lattice_vectors[0] + j*lattice_vectors[1] + center_pix
    valid = numpy.all(lower_bounds < lp, 1) * numpy.all(lp < upper_bounds, 1)
    lattice_points = list(lp[valid])
    if return_i_j:
        return (lattice_points,
                list(i[valid] - lattice_shift[0]),
                list(j[valid] - lattice_shift[1]))
    else:
        return lattice_points

def get_centered_subimage(
    center_point, window_size, image, background='none'):
    x, y = numpy.round(center_point).astype(int)
    xSl = slice(max(x-window_size-1, 0), x+window_size+2)
    ySl = slice(max(y-window_size-1, 0), y+window_size+2)
    subimage = numpy.array(image[xSl, ySl])
    if background != 'none':
        subimage -= background[xSl, ySl]
    interpolation.shift(
        subimage, shift=(x, y)-center_point, output=subimage)
    return subimage[1:-1, 1:-1]

def join_enderlein_images(
    data_filenames_list,
    new_grid_xrange, new_grid_yrange,
    join_widefield_images=True
    ):
    if len(data_filenames_list) < 2:
        print "Less than two files to join. Skipping..."
        return None
    print "Joining enderlein and widefield images into stack..."
    enderlein_stack = numpy.zeros(
        (len(data_filenames_list), new_grid_xrange[2], new_grid_yrange[2]),
        dtype=numpy.float)
    if join_widefield_images:
        widefield_stack = numpy.zeros(
            (len(data_filenames_list), new_grid_xrange[2], new_grid_yrange[2]),
            dtype=numpy.float)
    for i, d in enumerate(data_filenames_list):
        sys.stdout.write(
            '\rLoading file %i of %i'%(i, len(data_filenames_list)))
        sys.stdout.flush()
        basename = os.path.splitext(d)[0]
        enderlein_image_name = basename + '_enderlein_image.raw'
        widefield_image_name = basename + '_widefield.raw'
        try:
            enderlein_stack[i, :, :] = numpy.fromfile(
                enderlein_image_name, dtype=numpy.float).reshape(
                new_grid_xrange[2], new_grid_yrange[2])
        except ValueError:
            print "\n\nWARNING: the data file:"
            print enderlein_image_name
            print "may not be the size it was expected to be.\n\n"
            raise
        if join_widefield_images:
            try:
                widefield_stack[i, :, :] = numpy.fromfile(
                    widefield_image_name, dtype=numpy.float).reshape(
                    new_grid_xrange[2], new_grid_yrange[2])
            except ValueError:
                print "\n\nWARNING: the data file:"
                print widefield_image_name
                print "may not be the size it was expected to be.\n\n"
                raise

    stack_basename = os.path.commonprefix(data_filenames_list).rstrip(
        '0123456789')
    print "\nStack basename:", stack_basename
    enderlein_stack.tofile(stack_basename + '_enderlein_stack.raw')
    if join_widefield_images:
        widefield_stack.tofile(stack_basename + '_widefield_stack.raw')
        w_notes = open(stack_basename + '_widefield_stack.txt', 'wb')
        w_notes.write("Left/right: %i pixels\r\n"%(widefield_stack.shape[2]))
        w_notes.write("Up/down: %i pixels\r\n"%(widefield_stack.shape[1]))
        w_notes.write("Number of images: %i\r\n"%(widefield_stack.shape[0]))
        w_notes.write("Data type: 64-bit real\r\n")
        w_notes.write("Byte order: Intel (little-endian))\r\n")
        w_notes.close()
    e_notes = open(stack_basename + '_enderlein_stack.txt', 'wb')
    e_notes.write("Left/right: %i pixels\r\n"%(enderlein_stack.shape[2]))
    e_notes.write("Up/down: %i pixels\r\n"%(enderlein_stack.shape[1]))
    e_notes.write("Number of images: %i\r\n"%(enderlein_stack.shape[0]))
    e_notes.write("Data type: 64-bit real\r\n")
    e_notes.write("Byte order: Intel (little-endian))\r\n")
    e_notes.close()
    print "Done joining."
    return None

def get_data_locations():
    """Assumes that hot_pixels.txt and background.raw are in the same
    directory ast array_illumination.py"""
    import Tkinter, tkFileDialog, tkSimpleDialog, glob, array_illumination

    module_dir = os.path.dirname(array_illumination.__file__)
    background_filename = os.path.join(module_dir, 'background.raw')

    tkroot = Tkinter.Tk()
    tkroot.withdraw()
    data_filename = str(os.path.normpath(tkFileDialog.askopenfilename(
        title=("Select one of your raw SIM data files"),
        filetypes=[('Raw binary', '.raw')],
        defaultextension='.raw',
        initialdir=os.getcwd()
        ))) #Careful about Unicode here!
    data_dir = os.path.dirname(data_filename)

    while True:
        wildcard_data_filename = tkSimpleDialog.askstring(
            title='Filename pattern',
            prompt=("Use '?' as a wildcard\n\n" +
                    "For example:\n" +
                    "  image_????.raw\n" +
                    "would match:\n" +
                    "  image_0001.raw\n" +
                    "  image_0002.raw\n" +
                    "  etc...\n" +
                    "but would not match:\n" +
                    "   image_001.raw"),
            initialvalue=os.path.split(data_filename)[1])
        data_filenames_list = sorted(glob.glob(
            os.path.join(data_dir, wildcard_data_filename)))
        print "Data filenames:"
        for f in data_filenames_list:
            print '.  ' + f
        response = raw_input("Are those the files you want to process? [y]/n:")
        if response == 'n':
            continue
        else:
            break

    lake_filename = str(os.path.normpath(tkFileDialog.askopenfilename(
        title=("Select your lake calibration raw data file"),
        filetypes=[('Raw binary', '.raw')],
        defaultextension='.raw',
        initialdir=os.path.join(data_dir, os.pardir),
        initialfile='lake.raw'
        ))) #Careful about Unicode here!

    tkroot.destroy()
    return data_dir, data_filenames_list, lake_filename, background_filename

def use_lake_parameters():
    import  Tkinter, tkMessageBox
    tkroot = Tkinter.Tk()
    tkroot.withdraw()
    use_all_lake_parameters = tkMessageBox.askyesno(
        default=tkMessageBox.NO,
        icon=tkMessageBox.QUESTION,
        message="Use lake to determine offset?\n(Useful for sparse samples)",
        title='Offset calculation')
    tkroot.destroy()
    return use_all_lake_parameters

if __name__ == '__main__':
    get_data_locations()

#####
#####   Leftover code from when I was doing triangulation myself.            
#####
##def same_side(point_1, point_2, corner_1, corner_2):
##    cp1 = numpy.cross(
##        (corner_2[0] - corner_1[0], corner_2[1] - corner_1[1]),
##        (point_1[0] - corner_1[0], point_1[1] - corner_1[1]))
##    cp2 = numpy.cross(
##        (corner_2[0] - corner_1[0], corner_2[1] - corner_1[1]),
##        (point_2[0] - corner_1[0], point_2[1] - corner_1[1]))
##    if numpy.dot(cp1, cp2) > 0:
##        return True
##    return False
##
##def in_triangle(point, corners):
##    a, b, c = corners
##    if same_side(point, a, b, c):
##        if same_side(point, b, a, c):
##            if same_side(point, c, a, b):
##                return True
##    return False
##
##def find_bounding_triangle(point, possible_corners):
##    for corners in combinations(possible_corners, 3):
##        if in_triangle(point, corners):
##            return corners
##    raise UserWarning("Point not contained in corners")

####
####    Leftover code from when I was doing interpolation myself
####
##def three_point_weighted_average(position, corners, values):
##    """Given three 2D positions, and three values, computes a weighted
##    average of the values for some interior position. Equivalent to
##    interpolating with a plane."""
##    x, y = position
##    ((x1, y1), (x2, y2), (x3, y3)) = corners
##    (z1, z2, z3) = values
##    denom = y1*(x3 - x2) + y2*(x1 - x3) + y3*(x2 - x1)
##    w1 = (y3 - y2)*x + (x2 - x3)*y + x3*y2 - x2*y3
##    w2 = (y1 - y3)*x + (x3 - x1)*y + x1*y3 - x3*y1
##    w3 = (y2 - y1)*x + (x1 - x2)*y + x2*y1 - x1*y2
##    return (w1*z1 + w2*z2 + w3*z3) * -1.0 / denom

##"""Leftover code from a different interpolation approach"""
##from scipy.spatial import Delaunay
##def find_interpolation_neighbors(
##    new_grid_x, new_grid_y,
##    direct_lattice_vectors, shift_vector, offset_vector,
##    num_steps=186, display=False):
##    """We want to convert our scattered scan grid to the Cartesian
##    grid that Enderlein's trick expects. For each point on the desired
##    grid, this function finds three neighboring scattered scan points
##    suitable for interpolating the value at the desired point."""
##    """Represent the new grid in terms of lattice coordinates"""
##    new_grid = numpy.array(numpy.meshgrid(#Arguments backwards from expected!
##        new_grid_y, new_grid_x))[::-1, :, :].reshape(
##            2, new_grid_x.size*new_grid_y.size)
##    V = numpy.vstack(direct_lattice_vectors[:2]).T
##    new_grid_lattice_coordinates = numpy.linalg.solve(#Lattice coordinates
##        V, new_grid - offset_vector.reshape(2, 1)) #Relative to central spot
##    #Return to pixel coordinates, but now modulo the unit cell
##    new_grid_in_unit_cell = numpy.dot(
##        V, numpy.mod(new_grid_lattice_coordinates, 1))
##    if display:
##        response = raw_input("Plot new grid? y/[n]:")
##        if response == 'y':
##            print "Plotting new grid..."
##            fig = pylab.figure()
##            for i in range(2):
##                pylab.subplot(1, 2, i+1)
##                pylab.imshow(
##                    new_grid_in_unit_cell.reshape(
##                        2, new_grid_x.size, new_grid_y.size)[i, :, :],
##                    interpolation='nearest')
##            fig.show()
##    """Represent the illumination grid in terms of lattice coordinates"""
##    scan_positions = shift_vector * numpy.arange(num_steps
##                                                 ).reshape(num_steps, 1)
##    scan_positions_lattice_coordinates = numpy.linalg.solve(V, scan_positions.T)
##    scan_positions_in_unit_cell = numpy.dot(
##        V, numpy.mod(scan_positions_lattice_coordinates, 1))
##    scan_positions_in_padded_cell = [scan_positions_in_unit_cell +
##                                     i*direct_lattice_vectors[0].reshape(2, 1) +
##                                     j*direct_lattice_vectors[1].reshape(2, 1)
##                                     for i in (0, -1, 1)
##                                     for j in (0, -1, 1)]
##    """Triangulate the illumination grid"""
##    print "Triangulating..."
##    triangles = Delaunay(numpy.concatenate(
##        scan_positions_in_padded_cell, axis=1).T)
##    print "Done."
##    if display:
##        response = raw_input("Plot triangles? y/[n]:")
##        if response == 'y':
##            print "Plotting triangles..."
##            fig = pylab.figure()
##            for p in scan_positions_in_padded_cell:
##                pylab.plot(p[1, :], p[0, :], '.')
##            pylab.axis('equal')
##            fig.show()
##            fig = pylab.figure()
##            for t in triangles.points[triangles.vertices]:
##                pylab.plot(list(t[:, 1]) + [t[0, 1]],
##                           list(t[:, 0]) + [t[0, 0]], 'r-')
##            pylab.axis('equal')
##            fig.show()
##    """Search the illumination grid for the new grid points"""
##    print "Finding bounding triangles..."
##    simplices = triangles.find_simplex(new_grid_in_unit_cell.T)
##    print "Done."
##    if display:
##        print "Plotting a few spots in their triangles..."
##        fig = pylab.figure()
##        i_start = new_grid_x.size//2
##        j_start = new_grid_y.size//2
##        while True:
##            response = raw_input("New grid i (q to quit):")
##            if response == 'q':
##                break
##            elif response == '':
##                j_start += 1
##                if j_start >= new_grid_y.size:
##                    j_start -= new_grid_y.size
##                    i_start += 1
##                    if i_start >= new_grid_x.size:
##                        i_start -= new_grid_x.size
##            else:
##                try:
##                    i_start = int(response)
##                except ValueError:
##                    pass
##                response = raw_input("New grid j:")
##                try:
##                    j_start = int(response)
##                except ValueError:
##                    pass
##            start = i_start * new_grid_y.size + j_start
##            pylab.clf()
##            pylab.plot(scan_positions_in_padded_cell[0][1, :],
##                       scan_positions_in_padded_cell[0][0, :], '.')
##            for i in range(start, start + 5):
##                p = new_grid_in_unit_cell[:, i]
##                t = triangles.points[triangles.vertices[simplices[i]]]
##                pylab.plot(p[1], p[0], 'rx')
##                pylab.plot(list(t[:, 1]) + [t[0, 1]],
##                           list(t[:, 0]) + [t[0, 0]], 'r-')
##            pylab.axis('equal')
##            pylab.title("i, j: %i, %i"%(i_start, j_start))
##            fig.show()
##            fig.canvas.draw()
##    """For each new grid point, in which three frames is it illuminated?"""
##    neighboring_vertices = triangles.vertices[simplices]
##    frames_with_neighboring_illumination = numpy.mod(neighboring_vertices,
##                                                     num_steps)
##    neighbor_relative_positions = triangles.points[
##        neighboring_vertices] - new_grid_in_unit_cell.T.reshape(
##            new_grid_in_unit_cell.shape[1], 1, 2)
##    neighbor_absolute_positions = (
##        neighbor_relative_positions +
##        new_grid.T.reshape(new_grid.shape[1], 1, 2))
##    xs, ys = new_grid_x.size, new_grid_y.size
##    return (new_grid.reshape(2, xs, ys),
##            frames_with_neighboring_illumination.T.reshape(3, xs, ys),
##            neighbor_absolute_positions.T.reshape(2, 3, xs, ys))

##"""Leftover code from a different interpolation approach"""
##def display_neighboring_frames(
##    data_source, xPix, yPix, zPix,
##    new_grid, frames_with_neighboring_illumination, neighbor_absolute_positions,
##    lattice_vectors, shift_vector, offset_vector,
##    intensities_vs_galvo_position, background_image,
##    mode='random'):
##    print "Displaying neighboring frames..."
##    """Display the neighboring frames"""
##    image_data = load_image_data(data_source, xPix, yPix, zPix)
##    from random import randint
##    fig = pylab.figure()
##    i = new_grid.shape[1]//2
##    j = new_grid.shape[2]//2
##    while True:
##        if mode == 'random':
##            i = randint(0, new_grid.shape[1] - 1)
##            j = randint(0, new_grid.shape[2] - 1)
##            raw_input('Hit enter to continue...\n')
##        elif mode == 'scan':
##            response = raw_input("Next frame, i [scan]:")
##            if response == '':
##                j += 1
##                if j >= new_grid.shape[2]:
##                    j -= new_grid.shape[2]
##                    i += 1
##                    if i >= new_grid.shape[1]:
##                        i -= new_grid.shape[1]
##                print "Moving to i, j =", i, j
##            elif response == 'q' or response == 'e' or response == 'x':
##                break
##            else:
##                try:
##                    i = int(response)
##                except ValueError:
##                    pass
##                response = raw_input("Next frame, j:")
##                try:
##                    j = int(response)
##                except ValueError:
##                    pass
##                if i > new_grid.shape[1]: i = new_grid.shape[1] - 1
##                if i < 0: i = 0
##                if j > new_grid.shape[2]: j = new_grid.shape[2] - 1
##                if j < 0: j = 0
##
##        get_scan_point_neighbors(
##            new_grid[:, i, j],
##            frames_with_neighboring_illumination[:, i, j],
##            neighbor_absolute_positions[:, :, i, j],
##            image_data, background_image,
##            lattice_vectors, offset_vector, shift_vector,
##            intensities_vs_galvo_position,
##            footprint=5, display=True)
##    return None

##"""Leftover code from a different interpolation approach"""
##def get_scan_point_neighbors(
##    position, neighbors, neighbor_positions,
##    image_data, background_image,
##    lattice_vectors, offset_vector, shift_vector,
##    intensities_vs_galvo_position=None,
##    footprint=5, display=False):
##
##    x, y = numpy.round(position)
##    if display:
##        print "Grid point", position, "has neighbors in frames", neighbors
##        print "with positions:"
##        for n_p in neighbor_positions:
##            print n_p
##        pylab.clf()
##        pylab.suptitle("Illumination near grid point at %0.2f, %0.2f"%(
##            position[0], position[1]))
##        print "x, y:", x, y
##
##    threeNeighbors = numpy.zeros((3, 2*footprint+1, 2*footprint+1)) + 1e-12
##    for c, f in enumerate(neighbors):
##        lattice_indices = numpy.linalg.solve(
##            numpy.vstack(lattice_vectors[:2]).T,
##            neighbor_positions[:, c] - offset_vector - f*shift_vector)
##        if intensities_vs_galvo_position == None:
##            calibration_weight = 1
##        else:
##            calibration_weight = intensities_vs_galvo_position.get(
##                (int(round(lattice_indices[0])),
##                 int(round(lattice_indices[1]))),
##                {}).get(f, numpy.inf)
##        showMe = get_centered_subimage(
##            center_point=position, #neighbor_positions[:, c],
##            window_size=footprint,
##            image=image_data[f, :, :], background=background_image)
##        if showMe.shape == threeNeighbors.shape[1:] and calibration_weight > 0:
##            threeNeighbors[c, :, :] = showMe * 1.0 / calibration_weight
##        if display:
##            print "Lattice indices:", lattice_indices
##            print "Calibration weight:",
##            print "%0.3f"%(calibration_weight)
##            print "Frame", "%03i"%(f), "has average value:",
##            print "%0.3f"%(showMe.mean()), "above background"
##            print "Normalized value:", "%0.3f"%(
##                showMe.mean() * 1.0 / calibration_weight)
##    if display:
##        fig = pylab.gcf()
##        fig.clf()
##        showMe = numpy.array(threeNeighbors).transpose(1, 2, 0)
##        if showMe.max() > showMe.min():
##            showMe -= showMe.min()
##            showMe *= 1.0 / showMe.max()
##        pylab.subplot(1, 2, 1)
##        pylab.title("Frames %i, %i, %i"%(
##            neighbors[0], neighbors[1], neighbors[2]))
##        pylab.imshow(showMe, interpolation='nearest')
##        central_dot = numpy.zeros(threeNeighbors.shape[1:] + (4,))
##        central_dot[footprint, footprint, 0::3] = 1
##        pylab.imshow(central_dot, interpolation='nearest')
##        pylab.subplot(1, 2, 2)
##        pylab.plot(list(neighbor_positions[1, :]) + [neighbor_positions[1, 0]],
##                   list(neighbor_positions[0, :]) + [neighbor_positions[0, 0]],
##                   'b.-')
##        pylab.plot(position[1], position[0], 'rx', markersize=20)
##        pylab.axis('equal')
##        pylab.grid()
##        ax = pylab.gca()
##        ax.set_ylim(ax.get_ylim()[::-1])
##        fig.show()
##        fig.canvas.draw()
##    return threeNeighbors

##def xy_to_lattice_index(
##    x, y, frame_number,
##    lattice_vectors, offset_vector, shift_vector,
##    tolerance=0.01):
##
##    lattice_position = numpy.linalg.solve(
##        numpy.vstack(lattice_vectors[:2]).T,
##        numpy.array(x, y) -
##        offset_vector - frame_number*shift_vector)
##
##    lattice_indices = lattice_position.astype(int)
##    if ((lattice_indices - lattice_position)**2).sum() > tolerance:
##        print "Lattice indices:", lattice_indices
##        print "Lattice position:", lattice_position
##        raise UserWarning(
##            "Conversion to lattice index exceeded error tolerance")
##    return tuple(lattice_indices)
##
##def lattice_index_to_xy(
##    i, j, frame_number,
##    lattice_vectors, offset_vector, shift_vector):
##
##    return (i*lattice_vectors[0] + j*lattice_vectors[1] +
##            offset_vector +
##            frame_number*shift_vector)

    
    
