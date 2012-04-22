import sys, cPickle, numpy, pylab
from scipy.ndimage import gaussian_filter
poisson = numpy.vectorize(numpy.random.poisson)

pylab.close('all')

def generate_lattice(
    image_shape, lattice_vectors, center_pix='image', edge_buffer=2):

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

    num_vectors = int(#Probably an overestimate
        max(image_shape) / numpy.sqrt(lattice_vectors[0]**2).sum())
    lower_bounds = (edge_buffer, edge_buffer)
    upper_bounds = (image_shape[0] - edge_buffer, image_shape[1] - edge_buffer)
    i, j = numpy.mgrid[-num_vectors:num_vectors, -num_vectors:num_vectors]
    i = i.reshape(i.size, 1)
    j = j.reshape(j.size, 1)
    lp = i*lattice_vectors[0] + j*lattice_vectors[1] + center_pix
    valid = numpy.all(lower_bounds < lp, 1) * numpy.all(lp < upper_bounds, 1)
    lattice_points = lp[valid]
    return lattice_points

half_distance = 8
step_size = 1
image_pix = (768, 1024)
preframes = 3

delta_x = int(numpy.round(2*half_distance))
delta_y = int(numpy.round(numpy.round(delta_x * 0.5 * numpy.sqrt(3))))
num_shifts = preframes + delta_x * delta_y / (step_size**2)
print "Delta x:", delta_x
print "Delta y:", delta_y
print "Step size:", step_size
print "Frames:", num_shifts
illumination_pattern = numpy.memmap(
    'illumination_pattern.raw', dtype=numpy.uint8, mode='w+',
    shape=(num_shifts, image_pix[0], image_pix[1]))

lattice_vectors=(numpy.array((delta_x, 0)),
                 numpy.array((delta_x //2, delta_y)),
                 numpy.array((-delta_x//2, -delta_y)))
offset_vector = numpy.array((illumination_pattern.shape[0]//2,
                             illumination_pattern.shape[1]//2))

sh = preframes - 1 #First few frames are blank, 'cause our camera is craaaazy
for y in range(0, delta_y, step_size):
    for x in range(0, delta_x, step_size):
        sh += 1
        positions = generate_lattice(
            lattice_vectors=lattice_vectors,
            image_shape=illumination_pattern.shape[1:],
            center_pix=offset_vector + numpy.array((x, y)))
        print "Generating slice %i with %i spots..."%(sh, positions.shape[0])
        for p in positions:
            i, j = p
            """Add a PSF to the grid"""
            try:
                illumination_pattern[sh, i:i+1, j:j+1] = 255
            except IndexError:
                print "Skipping spot at", i, j
##        if sh == 0:
##            print "Plotting a representative frame..."
##            fig = pylab.figure()
##            pylab.imshow(gaussian_filter(illumination_pattern[sh, :, :].astype(float), sigma=5),
##                         cmap=pylab.cm.gray, interpolation='nearest')
##            pylab.colorbar()
##            fig.show()
##            fig.canvas.draw()
##            raw_input('Hit enter to continue...')


metadata = open('illumination_pattern.txt', 'wb')
metadata.write('Data type: 8-bit unsigned integers\r\n')
metadata.write('Dimensions: %i by %i pixels\r\n'%(
    illumination_pattern.shape[2], illumination_pattern.shape[1]))
metadata.write('Slices: %i\r\n'%(illumination_pattern.shape[0]))
metadata.close()

