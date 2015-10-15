import pprint
import numpy
from scipy.optimize import leastsq
from simple_tiff import simple_tif_to_array

measured_psf = simple_tif_to_array('psf.tif')
print measured_psf.shape
""""
A superposition of a few small Gaussian PSFs that sum up to an
approximation of our experimental PSF. They're characterized by
x-width, y-width, z-width, x-position, y-position, and z-position.
"""

def approximate_psf(widths_positions_and_amplitudes, output_shape):
    psf = numpy.zeros(output_shape, dtype=numpy.float)
    zyx = []
    for i in range(3):
        shape = [1, 1, 1]
        shape[i] = psf.shape[i]
        zyx.append(numpy.arange(psf.shape[i]).reshape(shape) -
                   0.5*(psf.shape[i] - 1))
    z, y, x = zyx
    wpa = wpa_vector_to_dict(widths_positions_and_amplitudes)
    background_level = wpa['background_level']
    for i in wpa.keys():
        try:
            int(i)
        except ValueError:
            continue
        r = wpa[i]
        """
        Some blobs wander out of the volume. How come? Is this
        actually a good thing?
        """
        psf += (r['amp'] *
                numpy.exp(-0.5*((x - r['x_position'])/(r['x_width']))**2) *
                numpy.exp(-0.5*((y - r['y_position'])/(r['y_width']))**2) *
                numpy.exp(-0.5*((z - r['z_position'])/(r['z_width']))**2) )
    return background_level + psf

##def wpa_vector_to_dict(wpa):
##    info = {}
##    info['background_level'] = wpa[0]
##    for i in range((len(wpa) - 1) / 7):
##        info[i] = {}
##        r = info[i]
##        (r['x_width'], r['y_width'], r['z_width'],
##         r['x_position'], r['y_position'], r['z_position'],
##         r['amp']
##         ) = wpa[1 + 7*i:1 + 7*(i+1)]
##    return info
##
##def psf_approximation_error(widths_positions_and_amplitudes, measured_psf,
##                            non_integer_spacing_penalty=0
##                            ):
##    residuals = (
##        measured_psf - approximate_psf(widths_positions_and_amplitudes,
##                                       output_shape=measured_psf.shape)
##            ).reshape(measured_psf.size)
####    extra_residuals = non_integer_spacing_penalty * numpy.array(
####        differences(widths_positions_and_amplitudes))
####    residuals = numpy.concatenate((residuals, extra_residuals))
##    return residuals
##
##def differences(wpa):
##    wpa = wpa_vector_to_dict(wpa)
##    x_positions, y_positions, z_positions = [], [], []
##    for k in wpa.keys():
##        try:
##            int(k)
##        except ValueError:
##            continue
##        x_positions.append(wpa[k]['x_position'])
##        y_positions.append(wpa[k]['y_position'])
##        z_positions.append(wpa[k]['z_position'])
##    diffs = []
##    for p in (x_positions, y_positions, z_positions):
##        for i in range(len(p)):
##            for j in range(i+1, len(p)):
##                diffs.append(numpy.mod(p[i] - p[j], 1))
##    return diffs
##
##parameters = [
##    0,
##    1, 1, 1, 0, 0, 0, 1,
##    1, 1, 1, 1, 0, 0, 1,
##    1, 1, 1, -1, 0, 0, 1,
##    1, 1, 1, 0, 1, 0, 1,
##    1, 1, 1, 0, -1, 0, 1,
##    1, 1, 1, 0, 0, 1, 1, 
##    1, 1, 1, 0, 0, -1, 1
##    ]
##
##for non_integer_spacing_penalty in (0, .001, 0.1, 1):
##    print "Solving for PSF..."
##    parameters, success = leastsq(
##        func=psf_approximation_error,
##        x0=parameters,
##        args=(measured_psf, non_integer_spacing_penalty),
##        maxfev=50000)
##    print "Done"
##    pprint.pprint(wpa_vector_to_dict(parameters))
##    print "Differences:", differences(parameters)
##
##print "Done iterating"
##print "Parameters:"
##print
##print "Background:", parameters[0]
##print
##for i in range((len(parameters) - 1) / 7):
##    print "Blob", i, ':'
##    print '(sx, sy, sz):', parameters[1+7*i:4+7*i]
##    print 'x, y, z:', parameters[4+7*i:7+7*i]
##    print "Amplitude:", parameters[7+7*i]
##    print
##print success
##
##
##approx_psf = approximate_psf(
##    parameters, output_shape=measured_psf.shape)
##approx_psf.tofile('approx_psf.raw')
##print approx_psf.min(), approx_psf.max()
##
##import pylab
##fig = pylab.figure()
##pylab.subplot(2, 3, 1)
##pylab.imshow(approx_psf.max(axis=0),
##             cmap=pylab.cm.gray, interpolation='nearest')
##pylab.subplot(2, 3, 2)
##pylab.imshow(approx_psf.max(axis=1),
##             cmap=pylab.cm.gray, interpolation='nearest')
##pylab.subplot(2, 3, 3)
##pylab.imshow(approx_psf.max(axis=2),
##             cmap=pylab.cm.gray, interpolation='nearest')
##pylab.subplot(2, 3, 4)
##pylab.imshow(measured_psf.max(axis=0),
##             cmap=pylab.cm.gray, interpolation='nearest')
##pylab.subplot(2, 3, 5)
##pylab.imshow(measured_psf.max(axis=1),
##             cmap=pylab.cm.gray, interpolation='nearest')
##pylab.subplot(2, 3, 6)
##pylab.imshow(measured_psf.max(axis=2),
##             cmap=pylab.cm.gray, interpolation='nearest')
##fig.show()
