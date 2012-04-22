import numpy, pylab
import find_lattice

##def fftshow(a):
##    fig = pylab.gcf()
##    pylab.clf()
##    b = numpy.log(1 + numpy.abs(a))
##    pylab.imshow(numpy.fft.fftshift(b), interpolation='nearest', cmap=pylab.cm.gray)
##    fig.show()
##    fig.canvas.draw()

pylab.close('all')

data_source = 'Beads.raw'
print "Data source:", data_source

"""Find a set of shift vectors which characterize the illumination"""
(fourier_lattice_vectors, direct_lattice_vectors,
 shift_vector, offset_vector) = find_lattice.get_lattice_vectors(
     filename=data_source,
     xPix=512,
     yPix=512,
     zPix=201,
     extent=10,
     num_spikes=150,
     tilt_filter=False,
     tolerance=3.5,
     num_harmonics=3,
     verbose=True,
     display=True,
     animate=False,
     show_interpolation=False,
     show_lattice=True)
print "Lattice vectors:"
for v in direct_lattice_vectors:
    print v
print "Shift vector:"
print shift_vector
print "Initial position:"
print offset_vector
