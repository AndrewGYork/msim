import sys, os, numpy, pylab
import find_lattice

pylab.close('all')

"""Menagerie of data sources. Uncomment one of these lines:"""
data_source, xPix, yPix, zPix = 'QDots.raw', 512, 512, 201
##data_source, xPix, yPix, zPix = 'Beads.raw', 512, 512, 201
##data_source, xPix, yPix, zPix = 'big_QDots.raw', 1024, 1344, 201
##data_source, xPix, yPix, zPix = 'big_Beads.raw', 1024, 1344, 201
##data_source, xPix, yPix, zPix = 'big_2_Beads.raw', 1024, 1344, 201
##data_source, xPix, yPix, zPix = 'lake_1000_positions.raw', 1024, 1344, 1000
##data_source, xPix, yPix, zPix = 'beads_1000_positions.raw', 1024, 1344, 1000
##data_source, xPix, yPix, zPix = 'utubules_1.raw', 1024, 1344, 999
##data_source, xPix, yPix, zPix = 'utubules_2.raw', 1024, 1344, 999

data_dir = 'data'
data_source = os.path.join(os.getcwd(), data_dir, data_source)
print "Data source:", data_source

"""Find a set of shift vectors which characterize the illumination"""
(fourier_lattice_vectors, direct_lattice_vectors,
 shift_vector, offset_vector) = find_lattice.get_lattice_vectors(
     filename=data_source, xPix=xPix, yPix=yPix, zPix=zPix,
     extent=20, #Important to get this right
     num_spikes=150,
     tolerance=3.5,
     num_harmonics=3,
     outlier_phase=1.,
     verbose=False, #Useful for debugging
     display=False, #Useful for debugging
     animate=False, #Useful to see if 'extent' is right
     show_interpolation=False, #Fairly low-level debugging
     show_lattice=False) #Very useful for checking validity
print "Lattice vectors:"
for v in direct_lattice_vectors:
    print v
print "Shift vector:"
print shift_vector
print "Initial position:"
print offset_vector

##"""Show a representative region of the illumination scan pattern"""
##spots = find_lattice.show_illuminated_points(
##    direct_lattice_vectors, shift_vector, offset_vector='image',
##    xPix=50, yPix=50, step_size=1, num_steps=186)

"""Define a new Cartesian grid for Enderlein's trick:"""
new_grid_x = numpy.linspace(0, xPix-1, 1*xPix)
new_grid_y = numpy.linspace(0, yPix-1, 1*yPix)
"""Find scan points which neighbor the grid:"""
(new_grid,
 frames_with_neighboring_illumination,
 neighbor_absolute_positions) = find_lattice.find_interpolation_neighbors(
     new_grid_x, new_grid_y,
     direct_lattice_vectors, shift_vector, offset_vector,
     num_steps=186, display=False)

##"""Check if the interpolation neighbors are sane"""
##raw_input('Display?')
##find_lattice.display_neighboring_frames(
##    data_source, xPix, yPix, zPix,
##    new_grid, frames_with_neighboring_illumination, neighbor_absolute_positions)

"""Interpolate the neighboring illumination points to calculate
Enderlein-formatted data"""
num_steps = 186
window_footprint = 10
print "Loading raw image data..."
image_data = numpy.fromfile(#Load the whole damn thing into memory.
    data_source, dtype=numpy.uint16, count=xPix*yPix*num_steps
    ).reshape(num_steps, xPix, yPix)
enderlein_format = numpy.memmap(
    'enderlin_format.raw', dtype=float, mode='w+',
    shape=new_grid.shape[1:] + (2*window_footprint+1, 2*window_footprint+1))
print "Done."
for i in range(new_grid.shape[1]): #Loop over the new array one at a time
    sys.stdout.write("\rRow %i"%(i))
    sys.stdout.flush()
    for j in range(new_grid.shape[2]):
        position = new_grid[:, i, j]
        neighbors = frames_with_neighboring_illumination[:, i, j]
        neighbor_positions = neighbor_absolute_positions[:, :, i, j]

        x, y = numpy.round(position)
        if (x < window_footprint + 1) or (y < window_footprint + 1):
            continue #Ignore edge points
        if (x >= image_data.shape[1] - window_footprint - 1 or
            y >= image_data.shape[2] - window_footprint - 1):
            continue #Ignore edge points

        neighbor_images = []
        for which_frame in neighbors:
            neighbor_images.append(image_data[
                which_frame,
                x - window_footprint:x + window_footprint + 1,
                y - window_footprint:y + window_footprint + 1].astype(float))

        enderlein_format[i, j, :, :
                         ] = find_lattice.three_point_weighted_average(
                             position=position,
                             corners=neighbor_positions.T,
                             values=neighbor_images)
    

enderlein_format.flush()
fig = pylab.figure()
pylab.imshow(enderlein_format.sum(axis=-1).sum(axis=-1),
             interpolation='nearest', cmap=pylab.cm.gray)
fig.show()
##Average three subpixel-shifted images, with weights given by their positions
##Construct the weights





