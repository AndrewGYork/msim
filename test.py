import sys, os, numpy, pylab
import find_lattice

pylab.close('all')

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

"""Define a new Cartesian grid for Enderlein's trick"""
new_grid_x = numpy.linspace(0, 512, 500)
new_grid_y = numpy.linspace(0, 512, 505)
(new_grid,
 frames_with_neighboring_illumination,
 neighbor_absolute_positions) = find_lattice.find_interpolation_neighbors(
     new_grid_x, new_grid_y,
     direct_lattice_vectors, shift_vector, offset_vector,
     num_steps=186, display=False)

raw_input('Display?')
print "Displaying neighboring frames..."
"""Display the neighboring frames"""
image_data = find_lattice.load_image_data(data_source, xPix, yPix, zPix)
from random import randint
fig = pylab.figure()
while True:
    which_point = randint(0, new_grid.shape[1] - 1)
    p = new_grid[:, which_point]
    n = frames_with_neighboring_illumination[which_point]
    n_pos = neighbor_absolute_positions[which_point, :, :]
    print "Grid point", p, "has neighbors in frames", n
    print "with positions:"
    for n_p in n_pos:
        print n_p
    pylab.clf()
    pylab.suptitle("Illumination near grid point at %0.2f, %0.2f"%(
        p[0], p[1]))
    x, y = numpy.round(p)
    print "x, y:", x, y
    for i, f in enumerate(n):
        pylab.subplot(2, 2, i+1)
        showMe = numpy.array(image_data[f,
                                        max(x-20, 0):x+20,
                                        max(y-20, 0):y+20])
        try:
            showMe[20, 20] = showMe.max()
        except (ValueError, IndexError):
            pass
        pylab.imshow(showMe, cmap=pylab.cm.gray, interpolation='nearest')
        pylab.title("Frame %i"%(f))
    pylab.subplot(2, 2, 4)
    pylab.plot(list(n_pos[:, 1]) + [n_pos[0, 1]],
               list(n_pos[:, 0]) + [n_pos[0, 0]], 'b.-')
    pylab.plot(p[1], p[0], 'rx', markersize=20)
    pylab.axis('equal')
    pylab.grid()
    ax = pylab.gca()
    ax.set_ylim(ax.get_ylim()[::-1])
    fig.show()
    fig.canvas.draw()
    raw_input()












##neighbors, spot_images = (
##    find_lattice.find_closest_illumination(
##    data_source, direct_lattice_vectors, shift_vector, offset_vector,
##    xPix, yPix, zPix,
##    step_size=1, num_steps=186,
##    new_grid_x=new_grid_x, new_grid_y=new_grid_y,
##    window_size=8, scan_footprint=3,
##    verbose=True, display=True))
##
##enderlein_format = numpy.zeros(
##    (new_grid_x.size, new_grid_y.size) + spot_images.shape[1:])
##for x in range(10, enderlein_format.shape[0]-10):
##    for y in range(10, enderlein_format.shape[1]-10):
##        position=(x, y)
##        corners=neighbors[['x', 'y']][x, y, :]
##        values=spot_images[neighbors['which_spot'][x, y, :]]
##        enderlein_format[
##            x, y, :, :] = find_lattice.three_point_weighted_average(
##                position, corners, values)
##        print "Position:", position
##        print "Corners:"
##        for c in corners: print c
##        print "Values:"
##        for v in values: print v.shape, v.min(), v.max()
####        print enderlein_format[x, y, :, :]
##        raw_input()
####        if y%10 == 0:
####            sys.stdout.write('\r %i %i'%(x, y))
####            sys.stdout.flush()

        
