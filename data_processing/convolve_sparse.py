import time
import numpy

def convolve_sparse(a, locations_list, amplitude_list=None):
    if amplitude_list == None:
        amplitude_list = [1 for l in locations_list]
    assert len(locations_list) == len(amplitude_list)
    
    output = numpy.zeros_like(a)
    for j, location in enumerate(locations_list):
        assert len(location) == len(a.shape)
        input_slices = [
            slice(
                max(0, location[i]),
                min(a.shape[i], a.shape[i] + location[i]))
            for i in range(len(a.shape))]
        output_slices = [
            slice(
                max(0, -location[i]),
                min(a.shape[i], a.shape[i] - location[i]))
            for i in range(len(a.shape))]
        output[output_slices] += amplitude_list[j] * a[input_slices]
    return output
    

a = numpy.zeros((50, 500, 500))
a[3, 10, 10] = 1
location_list = [
    (-3, 0, 0),
    (1, 1, -1)
    ]

print "Convolving with list..."
start = time.time()
b = convolve_sparse(a, location_list)
end = time.time()
print "Done convolving."
print "Time:", end-start

import pylab
fig = pylab.figure()
pylab.imshow(b.max(axis=0), cmap=pylab.cm.gray, interpolation='nearest')
fig.show()
