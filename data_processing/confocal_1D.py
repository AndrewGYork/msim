import numpy, pylab

def density(x):
    x = numpy.asarray(x)
    sig = .1
    dens = numpy.zeros(x.shape)
    positions = (0,)
    for x0 in positions:
        dens = dens + (1./sig) * numpy.exp(-((x - x0)**2 * 1./sig**2))
    return dens

def excitation(x):
    x = numpy.asarray(x)
    sig = 1.
    return (1./sig) * numpy.exp(-(x**2 * 1./sig**2))

def emission_psf(x):
    x = numpy.asarray(x)
    sig = 1.
    return (1./sig) * numpy.exp(-(x**2 * 1./sig**2))

def normalize(x):
    return x * 1./x.max()

def normalize_by(x, y):
    return x * 1./y.max()

pylab.close('all')

coords = numpy.atleast_3d(numpy.linspace(-6, 6, 450))
rp = numpy.array(coords[:, :, :]).transpose(2, 0, 1)
r = numpy.array(coords[:, :, :]).transpose(1, 2, 0)
s = numpy.array(coords[:, :, :])

c = density(rp)
E = excitation(r - rp)
U = emission_psf(r - rp + s)
Irs = (U * E * c).sum(axis=2) #Sum over rp

#Add some noise:
numpy.random.seed(3)
Irs += 0.1 * Irs.max() * numpy.random.random(Irs.shape)

#Form a confocal projection:
measured_density = Irs.sum(axis=1)

pinhole = numpy.zeros((1, Irs.shape[1]))
pinhole_radius = 10
pinhole_offset = pinhole.shape[1]//2
pinhole[
    :, pinhole_offset - pinhole_radius:
    pinhole_offset + pinhole_radius + 1] = 1
pinhole_densities = []
shifts = [0]
shift_size = 20
for i in range(4):
    pinhole_densities.append((pinhole * Irs).sum(axis=1))
    pinhole = numpy.roll(pinhole, shift_size, axis=1)
    shifts.append(shifts[-1] + shift_size)

fig = pylab.figure()
pylab.title('I(r, s)')
pylab.imshow(Irs, interpolation='nearest', cmap=pylab.cm.gray,
             )#extent=(s.flat[0], s.flat[-1], r.flat[-1], r.flat[0]))
pylab.xlabel('Camera pixel')
pylab.ylabel('Scan position')
fig.show()

fig = pylab.figure()
pylab.subplot(1, 2, 1)
pylab.plot(rp[0, 0, :], normalize(c[0, 0, :]), '.-', label='Density')
pylab.plot(r[:, 0, 0], normalize(measured_density), '.-',
           label='Confocal measured density (no pinhole)')
for i, p in enumerate(pinhole_densities):
    pylab.plot(r[:, 0, 0], normalize_by(p, pinhole_densities[0]), '.-',
               label='Confocal measured density')
pylab.grid()
pylab.subplot(1, 2, 2)
pylab.plot(rp[0, 0, :], normalize(c[0, 0, :]), '.-', label='Density')
pylab.plot(r[:, 0, 0], normalize(measured_density), '.-',
           label='Confocal measured density (no pinhole)')
for i, p in enumerate(pinhole_densities):
    pylab.plot(r[shifts[i]//2:, 0, 0],
               normalize(p)[:p.shape[0] - shifts[i]//2], '.-',
               label='Confocal measured density')
##pylab.legend()
pylab.grid()
fig.show()

