import sys, cPickle, numpy, pylab
from scipy.ndimage import gaussian_filter
poisson = numpy.vectorize(numpy.random.poisson)

pylab.close('all')

def group_bin_2d(a, num):
    a = numpy.array(a)
    for i in range(2):
        a = a.reshape(a.shape[0], a.shape[1]/num, num).sum(axis=2).transpose()
    return a

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

half_distance = 21
step_size = 3
image_pix = (512, 512)
illumination_psf_sigma = 2.
emission_psf_sigma = 2.
upsample = 5
padding = 20

delta_x = 2*half_distance
delta_y = numpy.round(delta_x * 0.5 * numpy.sqrt(3))
num_shifts = delta_x * delta_y / (step_size**2)
print "Delta x:", delta_x
print "Delta y:", delta_y
print "Step size:", step_size
print "Frames:", num_shifts
emission_intensity = numpy.memmap(
    'emission_intensity.raw', dtype=numpy.float, mode='w+',
    shape=(num_shifts, image_pix[0]+2*padding, image_pix[1]+2*padding))
background_level = 100
emission_intensity += background_level

upsampled_illumination = numpy.zeros((upsample*(image_pix[0]+2*padding),
                                      upsample*(image_pix[1]+2*padding)),
                                     dtype=numpy.float)

print "Generating test object..."
numpy.random.seed(0)
##"""Uniform object:"""
##upsampled_object = numpy.ones_like(upsampled_illumination)
##counts_per_molecule = 1e5
##"""Randomly placed point emitters:"""
##upsampled_object = numpy.ones_like(upsampled_illumination)
##upsampled_object *= (
##    numpy.random.random(size=upsampled_object.shape) > (1 - 1e-4))
##counts_per_molecule = 1e8
"""Thin lines: (only works for 512x512, upsample=5)"""
upsampled_object = numpy.zeros_like(upsampled_illumination)
upsampled_object[upsample*padding:-upsample*padding,
                 upsample*padding:-upsample*padding] = numpy.fromfile(
                     'Lines.raw', dtype=numpy.uint16).reshape(512*5, 512*5)
counts_per_molecule = 5e1
print "Plotting blurred version of the test object..."
showMe = gaussian_filter(upsampled_object, sigma=upsample*emission_psf_sigma)
fig = pylab.figure()
pylab.imshow(showMe, cmap=pylab.cm.gray, interpolation='nearest')
pylab.colorbar()
fig.show()
fig.canvas.draw()
raw_input("Hit enter to continue...")
pylab.close(fig)

lattice_vectors=(numpy.array((delta_x, 0)),
                 numpy.array((delta_x //2, delta_y)),
                 numpy.array((-delta_x//2, -delta_y)))
offset_vector = numpy.array((emission_intensity.shape[0]//2,
                             emission_intensity.shape[1]//2))

photoelectrons = numpy.memmap(
    'fake_background.raw', dtype=numpy.uint16, mode='w+',
    shape=(num_shifts, image_pix[0], image_pix[1]))
print
for p in range(photoelectrons.shape[0]):
    sys.stdout.write("\rAdding Poisson noise to background slice %i"%(p))
    sys.stdout.flush()
    photoelectrons[p, :, :] = poisson(
        emission_intensity[p, padding:-padding, padding:-padding]
        ).astype(numpy.uint16)
print
metadata = open('fake_background.txt', 'wb')
metadata.write('Data type: 16-bit unsigned integers\r\n')
metadata.write('Dimensions: %i by %i pixels\r\n'%(
    photoelectrons.shape[2], photoelectrons.shape[1]))
metadata.write('Slices: %i\r\n'%(photoelectrons.shape[0]))
metadata.close()
del photoelectrons

sh = -1
for y in range(0, int(delta_y), step_size):
    for x in range(0, int(delta_x), step_size):
        sh += 1
        upsampled_illumination.fill(0)
        positions = generate_lattice(
            lattice_vectors=lattice_vectors,
            image_shape=emission_intensity.shape[1:],
            center_pix=offset_vector + numpy.array((x, y)))
        print "Generating slice %i with %i spots..."%(sh, positions.shape[0])
        for p in positions:
            i, j = numpy.round((upsample * p)).astype(int)
            """Add a PSF to the grid"""
            try:
                upsampled_illumination[i, j] = 1
            except IndexError:
                pass
        print " Filtering illumination spots..."
        gaussian_filter(
            upsampled_illumination, sigma=upsample*illumination_psf_sigma,
            output=upsampled_illumination)
        blurred_illumination = upsampled_illumination
##        print "Plotting..."
##        fig = pylab.figure()
##        pylab.imshow(blurred_illumination, cmap=pylab.cm.gray, interpolation='nearest')
##        fig.show()
##        fig.canvas.draw()
        print " Binning and blurring emission..."
        emission_intensity[sh, :, :] += counts_per_molecule * group_bin_2d(
            gaussian_filter(blurred_illumination * upsampled_object,
                            sigma=upsample*emission_psf_sigma),
            upsample)
        if sh == 0:
            print "Plotting a representative frame..."
            fig = pylab.figure()
            pylab.imshow(emission_intensity[sh, :, :],
                         cmap=pylab.cm.gray, interpolation='nearest')
            pylab.colorbar()
            fig.show()
            fig.canvas.draw()
            raw_input('Hit enter to continue...')


"""
Add noise to the grid
"""
print "Adding Poisson noise"
photoelectrons = numpy.memmap(
    'fake_data.raw', dtype=numpy.uint16, mode='w+',
    shape=(num_shifts, image_pix[0], image_pix[1]))
print
for p in range(photoelectrons.shape[0]):
    sys.stdout.write("\rAdding Poisson noise to slice %i"%(p))
    sys.stdout.flush()
    photoelectrons[p, :, :] = poisson(
        emission_intensity[p, padding:-padding, padding:-padding]
        ).astype(numpy.uint16)
print
metadata = open('fake_data.txt', 'wb')
metadata.write('Data type: 16-bit unsigned integers\r\n')
metadata.write('Dimensions: %i by %i pixels\r\n'%(
    photoelectrons.shape[2], photoelectrons.shape[1]))
metadata.write('Slices: %i\r\n'%(photoelectrons.shape[0]))
metadata.close()
del photoelectrons

##photoelectrons = numpy.cumsum(photoelectrons, axis=2)
##print "Saving..."
##reordered = photoelectrons.astype(numpy.uint32).transpose((2, 0, 1))[
##    :, padding:-padding, padding:-padding]
##reordered.tofile('fake_lattice_cumsum.raw')
##metadata = open('fake_lattice_cumsum.txt', 'wb')
##metadata.write('Data type: 16-bit unsigned integers\r\n')
##metadata.write('Dimensions: %i by %i pixels\r\n'%(reordered.shape[1:]))
##metadata.write('Slices: %i\r\n'%(photoelectrons.shape[2]))
##metadata.close()
