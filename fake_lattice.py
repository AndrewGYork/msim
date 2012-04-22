import numpy, pylab

def roll2(a, vec):
    a = numpy.roll(a, vec[0], axis=0)
    return numpy.roll(a, vec[1], axis=1)

pylab.close('all')

dim = 400
sig = 2.2
x = numpy.arange(dim).reshape(dim, 1) - 0.5*dim
y = numpy.arange(dim).reshape(1, dim) - 0.5*dim
lump = numpy.exp(-(x**2 + y**2) / (2.*sig**2))

num = 30
im = numpy.zeros_like(lump)
vec_1 = numpy.array([15, -9])
vec_2 = numpy.array([15, 7])
for i in range(-num, num):
    for j in range(-num, num):
        vec = i*vec_1 + j*vec_2
        if numpy.abs(vec).max() > 0.47 * max(im.shape):
            continue
        else:
            im += roll2(lump, vec)

##bg = 0.01 * im.max() #Background
##im += bg
##
##tilt = x + y
##tilt -= tilt.mean()
##tilt *= 0.5 / tilt.max()
##tilt += 1
##im *= tilt #Charge transfer losses

##im -= tilt * bg

fftAbs = numpy.zeros_like(im)
for shift in range(2):
    fftAbs += abs(numpy.fft.fftn(numpy.roll(im, shift, axis=1)))

showMe = numpy.fft.fftshift(numpy.log(1 + fftAbs))

area = numpy.cross(vec_1, vec_2)
rotate_90 = ((0, -1.), (1., 0))
b_1 = numpy.dot(vec_2, rotate_90) * im.shape  / area
b_2 = numpy.dot(vec_1, rotate_90) * im.shape  / area
print b_1
print b_2
overlay = numpy.zeros(showMe.shape + (4,))
for vec in (vec_1, vec_2):
    for s in (1, -1):
        overlay[int(s * vec[0]), int(s * vec[1]), 0::3] = 1
for vec in (b_1, b_2):
    for s in range(-7, 7):
        overlay[int(round(s * vec[0])), int(round(s * vec[1])), 1::2] = 1
overlay = numpy.fft.fftshift(overlay, axes=[0, 1])

fig = pylab.figure()
pylab.subplot(1, 2, 1)
pylab.imshow(im, cmap=pylab.cm.gray, interpolation='nearest')
pylab.subplot(1, 2, 2)
pylab.imshow(showMe, cmap=pylab.cm.gray, interpolation='nearest')
pylab.imshow(overlay, interpolation='nearest')
fig.show()

