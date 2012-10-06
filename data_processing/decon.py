import time
import numpy, pylab
from scipy.ndimage import gaussian_filter
##from scipy.fftpack import fftn, ifftn

print "Loading data..."
data = numpy.fromfile("200nm_steps_cropped.raw", dtype=numpy.uint16
                      ).astype(numpy.float).reshape(51, 406, 487)
print "Done loading."

##small_psf = numpy.fromfile('approx_psf.raw', dtype=numpy.float
##                           ).reshape(11, 14, 14)
##psf = numpy.pad()
##otf = fftn(psf)

fwhm = (2, 3.5, 3.5)

fwhm_to_sigma = 2*numpy.sqrt(2*numpy.log(2))
print fwhm_to_sigma
sigma = (1.0 / fwhm_to_sigma) * numpy.asarray(fwhm)
def blur(x):
    return gaussian_filter(x, sigma)

"""
Iteration:
estimate *= Blur(measured/Blur(estimate))
"""

total_brightness = 1.0 * data.sum()
print data.shape
estimate = data.copy()
steps = 40
history = numpy.zeros(((steps+1,) + data.shape[1:]))
history[0, :, :] = total_brightness * (estimate.max(axis=0) /
                                       estimate.max(axis=0).sum())

##fig = pylab.figure()
for i in range(steps):
    print "Calculating iteration %i..."%(i)
    start = time.time()
    estimate *= blur(data /
                     blur(estimate))
    end = time.time()
    print "Done calculationg iteration %i."%(i)
    print "Elapsed time:", end-start
    estimate *= total_brightness / estimate.max(axis=0).sum()
    history[i, :, :] = estimate.max(axis=0)

estimate.tofile('estimate.raw')
history.tofile('history.raw')
