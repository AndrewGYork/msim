import sys, os, numpy, pylab
import find_lattice
from scipy.ndimage import gaussian_filter, interpolation
from scipy.signal import gaussian

pylab.close('all')

"""Default values, might be overwritten below:"""
num_harmonics = 3

"""Menagerie of data sources. Uncomment one of these lines:"""
##data_filename, xPix, yPix, zPix = 'QDots.raw', 512, 512, 201
##data_filename, xPix, yPix, zPix = 'Beads.raw', 512, 512, 201
##data_filename, xPix, yPix, zPix = 'big_QDots.raw', 1024, 1344, 201
##data_filename, xPix, yPix, zPix = 'big_Beads.raw', 1024, 1344, 201
##data_filename, xPix, yPix, zPix = 'big_2_Beads.raw', 1024, 1344, 201
##data_filename, xPix, yPix, zPix = 'lake_1000_positions.raw', 1024, 1344, 1000
##data_filename, xPix, yPix, zPix = 'beads_1000_positions.raw', 1024, 1344, 1000
##data_filename, xPix, yPix, zPix = 'utubules_1000_1.raw', 1024, 1344, 999
##data_filename, xPix, yPix, zPix = 'utubules_1000_2.raw', 1024, 1344, 999
##data_filename, xPix, yPix, zPix, steps, extent = 'Lake_1.raw', 1024, 1344, 200, 185, 9
##data_filename, xPix, yPix, zPix, steps = 'Lake_2.raw', 1024, 1344, 200, 186
##data_filename, xPix, yPix, zPix, steps = 'Lake_3.raw', 1024, 1344, 200, 187
##data_filename, xPix, yPix, zPix, steps = 'Lake_0p89uW.raw', 1024, 1344, 200, 188
##data_filename, xPix, yPix, zPix, steps, extent = 'Lake_1p40uW.raw', 1024, 1344, 200, 188, 9
##data_filename, xPix, yPix, zPix, steps, extent = 'Lake_1p96uW.raw', 1024, 1344, 200, 188, 9
##data_filename, xPix, yPix, zPix, steps = 'utubules_z0p00.raw', 1024, 1344, 200, 188
data_filename, xPix, yPix, zPix, steps, extent = 'fake_lake.raw', 512, 512, 200, 185, 8
##data_filename, xPix, yPix, zPix, steps, extent = 'fake_beads.raw', 512, 512, 200, 185, 8
##data_filename, xPix, yPix, zPix, steps, extent = 'fake_tubules.raw', 512, 512, 200, 185, 8
##data_filename, xPix, yPix, zPix, steps, extent = 'fake_tubules_sigma_1p00.raw', 512, 512, 200, 185, 8
##data_filename, xPix, yPix, zPix, steps, extent = 'Tubules_sapun_1.raw', 1024, 1344, 200, 188, 9
##data_filename, xPix, yPix, zPix, steps, extent = 'Tubules_sapun_2.raw', 1024, 1344, 200, 188, 9
##data_filename, xPix, yPix, zPix, steps, extent = 'Lake_sapun_2.raw', 1024, 1344, 200, 185, 9


lake_filename = 'fake_lake.raw'
background_filename, background_zPix = 'fake_lake_background.raw', 200
##lake_filename = 'Lake_sapun_2.raw'
##background_filename, background_zPix = 'Lake_0p00uW.raw', 200

data_dir = 'data'
data_filename = os.path.join(os.getcwd(), data_dir, data_filename)
lake_filename = os.path.join(os.getcwd(), data_dir, lake_filename)
background_filename = os.path.join(os.getcwd(), data_dir, background_filename)
print "Data source:", data_filename
print "Calibration source:", lake_filename
print "Background source:", background_filename

"""Find a set of shift vectors which characterize the illumination"""
print "\nDetecting illumination lattice parameters..."
(fourier_lattice_vectors, direct_lattice_vectors,
 shift_vector, offset_vector) = find_lattice.get_lattice_vectors(
     filename=data_filename, xPix=xPix, yPix=yPix, zPix=zPix,
     extent=extent, #Important to get this right. '20' for 1024/1344
     num_spikes=300,
     tolerance=3.5,
     num_harmonics=num_harmonics,
     outlier_phase=1.,
     verbose=False, #Useful for debugging
     display=False, #Useful for debugging
     animate=False, #Useful to see if 'extent' is right
     show_interpolation=False, #Fairly low-level debugging
     show_lattice=True) #Very useful for checking validity
print "Lattice vectors:"
for v in direct_lattice_vectors:
    print v
print "Shift vector:"
print shift_vector
print "Initial position:"
print offset_vector

(intensities_vs_galvo_position,
 background_frame) = find_lattice.spot_intensity_vs_galvo_position(
     lake_filename, xPix, yPix, zPix, extent,
     background_filename, background_zPix,
     window_size=10, verbose=True, show_steps=False, display=True)

##"""Show a representative region of the illumination scan pattern"""
##spots = find_lattice.show_illuminated_points(
##    direct_lattice_vectors, shift_vector, offset_vector='image',
##    xPix=500, yPix=500, step_size=1, num_steps=steps)

"""Define a new Cartesian grid for Enderlein's trick:"""
new_grid_x = numpy.linspace(0, xPix-1, xPix)
new_grid_y = numpy.linspace(0, yPix-1, yPix)

"""Interpolate the neighboring illumination points to calculate a
higher resolution image"""
window_footprint = 10 #For now, make this an even number
aperture_size = 2
show_steps = False
show_slices = False
verbose = True

basename = os.path.splitext(data_filename)[0]
enderlein_image_name = basename + '_enderlein_image.raw'

if os.path.exists(enderlein_image_name):
    print "\nEnderlein image already calculated."
    print "Loading", os.path.split(enderlein_image_name)[1]
    enderlein_image = numpy.fromfile(
        enderlein_image_name, dtype=float
        ).reshape(new_grid_x.shape[0], new_grid_y.shape[0])
else:
    print "\nCalculating Enderlein image"
    print
    if show_steps or show_slices: fig = pylab.figure()
    enderlein_image = numpy.zeros((new_grid_x.shape[0], new_grid_y.shape[0]))
    image_data = find_lattice.load_image_data(data_filename, xPix, yPix, zPix)
    aperture = gaussian(2*window_footprint+1, std=aperture_size
                        ).reshape(2*window_footprint+1, 1)
    aperture = aperture * aperture.T
    grid_step_x = new_grid_x[1] - new_grid_x[0]
    grid_step_y = new_grid_y[1] - new_grid_y[0]
    for z in range(steps):
        if verbose:
            sys.stdout.write("\rProcessing raw data image %i"%(z))
            sys.stdout.flush()
        lattice_points, i_list, j_list = find_lattice.generate_lattice(
            image_shape=(xPix, yPix),
            lattice_vectors=direct_lattice_vectors,
            center_pix=offset_vector + z*shift_vector,
            edge_buffer=window_footprint+1,
            return_i_j=True)
        for m, lp in enumerate(lattice_points):
            i, j = int(i_list[m]), int(j_list[m])
            """Take an image centered on each illumination point"""
            spot_image = find_lattice.get_centered_subimage(
                center_point=lp, window_size=window_footprint,
                image=image_data[z, :, :], background=background_frame)
            """Aperture the image with a synthetic pinhole"""
            intensity_normalization = 1.0 / intensities_vs_galvo_position.get(
                (i, j), {}).get(z, numpy.inf)
            if (intensity_normalization == 0 or
                spot_image.shape != (2*window_footprint+1, 2*window_footprint+1)
                ):
                continue #Skip to the next spot
            apertured_image = aperture * spot_image * intensity_normalization
            """Recenter the image on the nearest scan grid point"""
            nearest_grid_point = numpy.round(
                (lp - (new_grid_x[0], new_grid_y[0])) /
                (grid_step_x, grid_step_y))
            interpolation.shift(apertured_image,
            shift=(lp-nearest_grid_point), output=apertured_image)
            """Add the recentered image back to the scan grid"""
            if intensity_normalization > 0:
                enderlein_image[
                    nearest_grid_point[0]-window_footprint:
                    nearest_grid_point[0]+window_footprint+1,
                    nearest_grid_point[1]-window_footprint:
                    nearest_grid_point[1]+window_footprint+1,
                    ] += apertured_image
            if show_steps:
                pylab.clf()
                pylab.suptitle(
                    "Spot %i, %i in frame %i\nCentered at %0.2f, %0.2f"%(
                        i, j, z, lp[0], lp[1]))
                pylab.subplot(1, 2, 1)
                pylab.imshow(
                    spot_image, interpolation='nearest', cmap=pylab.cm.gray)
                pylab.subplot(1, 2, 2)
                pylab.imshow(
                    apertured_image, interpolation='nearest', cmap=pylab.cm.gray)
                fig.show()
                fig.canvas.draw()
                response = raw_input('Hit enter to continue, q to quit:')
                if response == 'q' or response == 'e' or response == 'x':
                    print "Done showing steps..."
                    show_steps = False
        if show_slices:
            pylab.clf()
            pylab.imshow(enderlein_image,
                         cmap=pylab.cm.gray, interpolation='nearest')
            fig.show()
            fig.canvas.draw()
            response=raw_input('Hit enter to continue...')


    
    enderlein_image.tofile(enderlein_image_name)
fig = pylab.figure()
pylab.imshow(enderlein_image,
             interpolation='nearest', cmap=pylab.cm.gray)
pylab.colorbar()
fig.show()
