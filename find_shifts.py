import sys
import numpy, pylab

def normalize(a):
    a = numpy.array(a)
    a -= a.min()
    a *= (1.0 / a.max())
    return a

pylab.close('all')

"""Load the raw data from the Visitech Infinity"""
xPix, yPix, zPix = 512, 512, 201
lake = 'QDots.raw'
beads = 'Beads.raw'
imageData = numpy.fromfile(
    lake, dtype=numpy.uint16
    ).reshape(zPix, xPix, yPix).transpose((1, 2, 0)).astype(float)

"""Crop the data"""
imageData = imageData[:, :, :]
print imageData.min(), imageData.max()

"""Find a set of shift vectors which characterize the illumination"""
x_s = numpy.array((228-33, 484-480)) * 1.0 / 200.
x_0 = numpy.array((188., 270.))

##x_1 = numpy.array((508-36, 8-297)) * 1.0 / 31.
##x_2 = numpy.array((506-57, 225-6)) * 1.0 / 30.
x_1 = numpy.array((-15.24110412, 9.27040961))
x_2 = numpy.array((14.9173426, 7.3195628))

print x_0
print x_1
print x_2
print x_s

"""Display the shift vectors to check their accuracy"""
fig = pylab.figure()
for s in range(imageData.shape[2]):
    pylab.clf()
    showMe = imageData[:, :, s]
    dots = numpy.zeros(list(showMe.shape) + [4])
    for p in range(-30, 30):
        for q in range(-30, 30):
            x = int(round(x_0[1] + p*x_1[1] + q*x_2[1] + s*x_s[1]))
            y = int(round(x_0[0] + p*x_1[0] + q*x_2[0] + s*x_s[0]))
            if 0 < x < dots.shape[0]:
                if 0 < y < dots.shape[1]:
                    dots[x, y, 0::3] = 1
    pylab.imshow(showMe, cmap=pylab.cm.gray, interpolation='nearest')
    pylab.imshow(dots, interpolation='nearest')
    fig.show()
    raw_input('.')
##    pylab.savefig('./pngs/shift_%04i.png'%(s))
    sys.stdout.write('\r%04i'%(s))
    sys.stdout.flush()

"""Find a mapping from pixel (m, n) to shift s"""
##shift = numpy.load('shift.npy')
distances = 9 * numpy.ones_like(imageData)
for s in range(imageData.shape[2]):
    sys.stdout.write('\r%04i'%(s))
    sys.stdout.flush()
    for p in range(-30, 30):
        for q in range(-30, 30):
            x = x_0[1] + p*x_1[1] + q*x_2[1] + s*x_s[1]
            y = x_0[0] + p*x_1[0] + q*x_2[0] + s*x_s[0]
            m = int(round(x))
            n = int(round(y))
            if 2 < x < distances.shape[0] - 2:
                if 2 < y < distances.shape[1] - 2:
                    for xS in (-1, 0, 1):
                        for yS in (-1, 0, 1):
                            distances[m + xS, n + xS, s] = (
                                (x - m - xS)**2 + (y - n - xS)**2)

"""Display the distance of the closest spot"""
fig = pylab.figure()
pylab.imshow(distances.min(axis=2), cmap=pylab.cm.gray, interpolation='nearest')
pylab.colorbar()
fig.show()

shift = distances.argmin(axis=2)
del distances
numpy.save('shift.npy', shift)

"""Rearrange the data to form a cartesian raster"""
xSize, ySize = 16, 16
rasterData = numpy.zeros(imageData.shape[:2] + (xSize, ySize))
for m in range(xSize//2, rasterData.shape[0] - xSize//2):
    sys.stdout.write('\r%04i'%(m))
    sys.stdout.flush()
    for n in range(ySize//2, rasterData.shape[1] - ySize//2):
        rasterData[m, n, :, :] = imageData[
            m-xSize//2:m+xSize//2,
            n-ySize//2:n+ySize//2,
            shift[m, n]]

"""Display the re-ordered data"""
fig = pylab.figure()
pylab.imshow(rasterData.sum(axis=3).sum(axis=2),
             cmap=pylab.cm.gray, interpolation='nearest')
fig.show()


fig = pylab.figure()
fig.show()
raw_input()
for m in range(8, rasterData.shape[0]):
    for n in range(8, rasterData.shape[1]):
        pylab.clf()
        pylab.imshow(rasterData[m, n, :, :],
                     cmap=pylab.cm.gray, interpolation='nearest')
        pylab.title('%i, %i'%(m, n))
        fig.show()
        fig.canvas.draw()

