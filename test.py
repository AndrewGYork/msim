import sys, os, numpy, pylab
import find_lattice

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
##data_filename, xPix, yPix, zPix, steps, extent = 'fake_lake.raw', 512, 512, 200, 185, 8
##data_filename, xPix, yPix, zPix, steps, extent = 'fake_beads.raw', 512, 512, 200, 185, 8
##data_filename, xPix, yPix, zPix, steps, extent = 'fake_tubules.raw', 512, 512, 200, 185, 8
data_filename, xPix, yPix, zPix, steps, extent = 'fake_tubules_sigma_1p00.raw', 512, 512, 200, 185, 8
##data_filename, xPix, yPix, zPix, steps, extent = 'Tubules_sapun_1.raw', 1024, 1344, 200, 188, 9
##data_filename, xPix, yPix, zPix, steps, extent = 'Tubules_sapun_2.raw', 1024, 1344, 200, 188, 9


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
new_grid_x = numpy.linspace(0, xPix, xPix)
new_grid_y = numpy.linspace(0, yPix, yPix)
"""Find scan points which neighbor the grid:"""
(new_grid,
 frames_with_neighboring_illumination,
 neighbor_absolute_positions) = find_lattice.find_interpolation_neighbors(
     new_grid_x, new_grid_y,
     direct_lattice_vectors, shift_vector, offset_vector,
     num_steps=steps, display=False)

"""Check if the interpolation neighbors are sane"""
find_lattice.display_neighboring_frames(
    data_filename, xPix, yPix, zPix,
    new_grid, frames_with_neighboring_illumination, neighbor_absolute_positions,
    direct_lattice_vectors, shift_vector, offset_vector,
    intensities_vs_galvo_position, background_frame,
    mode='scan')

"""Interpolate the neighboring illumination points to calculate
Enderlein-formatted data"""
num_steps = steps
window_footprint = 5


basename = os.path.splitext(data_filename)[0]
enderlein_format_name = basename + '_enderlein_format.raw'
enderlein_image_name = basename + '_enderlein_image.raw'

if (os.path.exists(enderlein_format_name) and
    os.path.exists(enderlein_image_name)):
    print "\nEnderlein format already calculated."
    print "Loading", os.path.split(enderlein_format_name)[1]
    enderlein_format = numpy.memmap(
        enderlein_format_name, dtype=float, mode='r',
        shape=new_grid.shape[1:] + (2*window_footprint+1, 2*window_footprint+1))
    print "Loading", os.path.split(enderlein_image_name)[1]
    simple_image = numpy.fromfile(
        enderlein_image_name, dtype=float).reshape(xPix, yPix)
else:
    print "\nCalculating Enderlein format data"
    print "Loading raw image data..."
    image_data = numpy.fromfile(#Load the whole damn thing into memory.
        data_filename, dtype=numpy.uint16, count=xPix*yPix*num_steps
        ).reshape(num_steps, xPix, yPix)
    enderlein_format = numpy.memmap(
        enderlein_format_name, dtype=float, mode='w+',
        shape=new_grid.shape[1:] + (2*window_footprint+1, 2*window_footprint+1))
    print "Done."
    for i in range(new_grid.shape[1]): #Loop over the new array one at a time
        sys.stdout.write("\rRow %i"%(i))
        sys.stdout.flush()
        for j in range(new_grid.shape[2]):
            position = new_grid[:, i, j]
            neighbors = frames_with_neighboring_illumination[:, i, j]
            neighbor_positions = neighbor_absolute_positions[:, :, i, j]

            neighbor_images = find_lattice.get_scan_point_neighbors(
                position, neighbors, neighbor_positions,
                image_data, background_frame,
                direct_lattice_vectors, offset_vector, shift_vector,
                intensities_vs_galvo_position,
                footprint=5)
##            x, y = numpy.round(position)
##            if (x < window_footprint + 3) or (y < window_footprint + 3):
##                continue #Ignore edge points
##            if (x >= (image_data.shape[1] - window_footprint - 3) or
##                y >= (image_data.shape[2] - window_footprint - 3)):
##                continue #Ignore edge points
##
##            neighbor_images = []
##            for wf, which_frame in enumerate(neighbors):
##                x_n, y_n = neighbor_positions[:, wf]
##                lattice_indices = tuple(numpy.round(numpy.linalg.solve(
##                    numpy.vstack(direct_lattice_vectors[:2]).T,
##                    neighbor_positions[:, wf] -
##                    offset_vector - which_frame*shift_vector)).astype(int))
##                calibration_factor = intensities_vs_galvo_position.get(
##                    lattice_indices, {}).get(which_frame, numpy.inf)
##                neighbor_images.append((1.0 / calibration_factor)*image_data[
##                    which_frame,
##                    round(x_n) - window_footprint:round(x_n) + window_footprint + 1,
##                    round(y_n) - window_footprint:round(y_n) + window_footprint + 1
##                    ].astype(float))
##                if neighbor_images[-1].shape != (2*window_footprint+1,
##                                                 2*window_footprint+1):
##                    neighbor_images[-1] = numpy.zeros((2*window_footprint+1,
##                                                       2*window_footprint+1))
            enderlein_format[i, j, :, :
                             ] = find_lattice.three_point_weighted_average(
                                 position=position,
                                 corners=neighbor_positions.T,
                                 values=neighbor_images)    

    enderlein_format.flush()
    simple_image = numpy.zeros(enderlein_format.shape[:2])
    print
    print "Constructing simple image..."
    for i in range(simple_image.shape[0]):
        sys.stdout.write("\rRow %i"%(i))
        sys.stdout.flush()
        for j in range(simple_image.shape[1]):
            simple_image[i, j] = enderlein_format[i, j, :, :].sum()
    simple_image.tofile(enderlein_image_name)
fig = pylab.figure()
pylab.imshow(simple_image,
             interpolation='nearest', cmap=pylab.cm.gray)
pylab.colorbar()
fig.show()
