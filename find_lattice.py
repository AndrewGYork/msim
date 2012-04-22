import os, sys, numpy, pylab
from itertools import product
from scipy.ndimage import gaussian_laplace
from scipy.signal import resample

def load_image_data(filename, xPix=512, yPix=512, zPix=201):
    """Load the 16-bit raw data from the Visitech Infinity"""
    return numpy.memmap(
        filename, dtype=numpy.uint16, mode='r',
        ).reshape(zPix, xPix, yPix) #FIRST dimension is image number

def get_fft_abs(filename, image_data):
    basename = os.path.splitext(filename)[0]
    fft_abs_name = basename + '_fft_abs.npy'
    fft_data_name = basename + '_fft_data.raw'
    
    if os.path.exists(fft_abs_name) and os.path.exists(fft_data_name):
        print "Loading", fft_abs_name
        fft_abs = numpy.load(fft_abs_name)
        print "Loading", fft_data_name
        fft_data = numpy.memmap(fft_data_name, dtype=numpy.complex128, mode='r'
                                ).reshape(image_data.shape)
    else:
        print "Generating fft_abs and fft_data"
        fft_data = numpy.memmap(fft_data_name, dtype=numpy.complex128,
                                mode='w+', shape=image_data.shape)
        fft_abs = numpy.zeros(image_data.shape[1:])
        for z in range(image_data.shape[0]):
            fft_data[z, :, :] = numpy.fft.fftn(image_data[z, :, :], axes=(0, 1))
            fft_abs += numpy.abs(fft_data[z, :, :])
            sys.stdout.write('\rProcessing slice %i'%(z+1))
            sys.stdout.flush()
        numpy.save(fft_abs_name, fft_abs)
        print
    return (fft_data, fft_abs)

def simple_max_finder(a, show_plots=True):
    """Given a 3x3 array with the maximum pixel in the center,
    estimates the x/y position of the true maximum"""

    true_max = []
    interpPoints = numpy.arange(-1, 2)
    for data in (a[:, 1], a[1, :]):
        myFit = numpy.poly1d(numpy.polyfit(
            interpPoints, data, deg = 2))
        true_max.append(-myFit[1]/(2.0*myFit[2]))
    true_max = numpy.array(true_max)

    if show_plots:
        print "Correction:", true_max
        fig = pylab.figure()
        pylab.subplot(1, 3, 1)
        pylab.imshow(a, interpolation='nearest', cmap=pylab.cm.gray)
        pylab.axhline(y=1 + true_max[0])
        pylab.axvline(x=1 + true_max[1])
        pylab.subplot(1, 3, 2)
        pylab.plot(a[:, 1])
        pylab.axvline(x=1 + true_max[0])
        pylab.subplot(1, 3, 3)
        pylab.plot(a[1, :])
        pylab.axvline(x=1 + true_max[1])
        fig.show()

    return true_max

def combinations_with_replacement(iterable, r):
    """
    >>>print([i for i in combinations_with_replacement(['a', 'b', 'c'], 2)])
    [('a', 'a'), ('a', 'b'), ('a', 'c'), ('b', 'b'), ('b', 'c'), ('c', 'c')]
    """
    pool = tuple(iterable)
    n = len(pool)
    for indices in product(range(n), repeat=r):
        if sorted(indices) == list(indices):
            yield tuple(pool[i] for i in indices)

def find_spikes(fftAbs, extent=10, num_spikes=150, tilt_filter=False,
                display=True, animate=False):
    """Finds spikes in the sum of the 2D ffts of an image stack"""
    log_fftAbs = numpy.log(1+fftAbs)
    center_pix = numpy.array(fftAbs.shape)//2

    if tilt_filter:
        """Remove the worst cross-convolution artifact from non-flat field"""
        dc_term = 1.0 * log_fftAbs[center_pix[0], center_pix[1]]

        right_edge = log_fftAbs[:, -10:].mean(axis=1)
        spike_magnitude = right_edge[center_pix[0]] - right_edge.mean()
        log_fftAbs[center_pix[0], :] -= spike_magnitude

        bottom_edge = log_fftAbs[-10:, :].mean(axis=0)
        spike_magnitude = bottom_edge[center_pix[1]] - bottom_edge.mean()
        log_fftAbs[center_pix[0], :] -= spike_magnitude

        log_fftAbs[center_pix[0], center_pix[1]] = dc_term

    lgl = -gaussian_laplace(log_fftAbs, sigma=1.5)
    lgl -= lgl.mean()
    lgl *= 1.0 / lgl.std()

    if display:
        fig = pylab.figure()
        pylab.imshow(
            numpy.array(lgl), cmap=pylab.cm.gray, interpolation='nearest',
            extent=[-0.5 - center_pix[1], lgl.shape[1] - 0.5 - center_pix[1],
                    lgl.shape[0] - 0.5 - center_pix[0], -0.5 - center_pix[0]])
        pylab.title('Filtered average Fourier magnitude')
        fig.show()

    coords = []
    if animate:
        fig = pylab.figure()
        print 'Center pixel:', center_pix
    for i in range(num_spikes):
        coords.append(
            numpy.array(numpy.unravel_index(lgl.argmax(), lgl.shape)))
        c = coords[-1]
        xSl = slice(max(c[0]-extent, 0), min(c[0]+extent, lgl.shape[0]))
        ySl = slice(max(c[1]-extent, 0), min(c[1]+extent, lgl.shape[1]))
        lgl[xSl, ySl] = 0
        if animate:
            print i, ':', c
            pylab.clf()
            pylab.subplot(1, 2, 1)
            pylab.imshow(lgl, cmap=pylab.cm.gray, interpolation='nearest')
            pylab.colorbar()
            pylab.subplot(1, 2, 2)
            pylab.plot(lgl.max(axis=1))
            fig.show()
            fig.canvas.draw()
            if i == 0:
                raw_input('.')

    coords = [c - center_pix for c in coords]
    coords = sorted(coords, key=lambda x: x[0]**2 + x[1]**2)

    return coords #Lattice k-vectors, sorted by vector magnitude
    
def test_basis(coords, basis_vectors, tolerance, verbose=False):
    #Checks for expected lattice, returns the points found and halts on failure.
    points_found = list(basis_vectors)
    num_vectors = 2
    searching = True
    while searching:
        if verbose: print "Looking for combinations of %i basis vectors."%(
            num_vectors)
        lattice = [sum(c) for c in
                 combinations_with_replacement(basis_vectors, num_vectors)]
        if verbose: print "Expected lattice points:", lattice
        for i, lat in enumerate(lattice):
            for c in coords:
                dif = numpy.sqrt(((lat - c)**2).sum())
                if dif < tolerance:
                    if verbose: print "Found lattice point:", c, dif
                    points_found.append(c)
                    break
            else: #Fell through the loop
                if verbose: print "Expected lattice point not found"
                searching = False
        if not searching: return (num_vectors, points_found)
        num_vectors += 1
    
def get_basis_vectors(fftAbs, coords, extent=10, tolerance=3.,
                      verbose=False, show_interpolation=False):
    for i in range(len(coords)): #Where to start looking.
        basis_vectors = []
        precise_basis_vectors = []
        for c, coord in enumerate(coords):
            if c < i:
                continue

            if c == 0:
                if max(abs(coord)) > 0:
                    print "c:", c
                    print "Coord:", coord
                    print "Coordinates:"
                    for x in coords: print x
                    raise UserWarning('No peak at the central pixel')
                else:
                    continue #Don't look for harmonics of the DC term

            if coord[0] < 0:
                #Ignore the negative versions
                if verbose: print "\nIgnoring:", coord
            else:
                #Check for harmonics
                if verbose: print "\nTesting:", coord
                num_vectors, points_found = test_basis(
                    coords, [coord], tolerance=tolerance, verbose=verbose)
                if num_vectors > 3:
                    #We found enough harmonics. Keep it, for now.
                    basis_vectors.append(coord)
                    center_pix = numpy.array(fftAbs.shape)//2
                    furthest_spike = points_found[-1] + center_pix
                    if verbose:
                        print "Appending", coord
                        print "%i harmonics found, at:"%(num_vectors-1)
                        for p in points_found:
                            print ' ', p
                    true_max = points_found[-1] + simple_max_finder(
                        fftAbs[furthest_spike[0] - 1:furthest_spike[0] + 2,
                               furthest_spike[1] - 1:furthest_spike[1] + 2],
                        show_plots=show_interpolation)

                    precise_basis_vectors.append(
                        true_max * 1.0 / len(points_found))
                    if verbose: print "Appending", precise_basis_vectors[-1]
                    if show_interpolation: raw_input('.')
                    if len(basis_vectors) > 1:
                        if verbose:
                            print "\nTesting combinations:", basis_vectors
                        num_vectors, points_found = test_basis(
                            coords, basis_vectors, tolerance=tolerance,
                            verbose=verbose)
                        if num_vectors > 3:
                            #The combination predicts the lattice
                            if len(basis_vectors) ==3:
                                #We're done; we have three consistent vectors.
                                precise_basis_vectors = sorted(
                                    precise_basis_vectors, key=lambda x: x[0])
                                precise_basis_vectors[-1] *= -1
                                return precise_basis_vectors
                        else:
                            #Blame the new guy, for now.
                            basis_vectors.pop()
                            precise_basis_vectors.pop()
    else:
        raise UserWarning(
            "Basis vector search failed. Diagnose by running with verbose=True")

def get_shift_vector(
    fourier_lattice_vectors, fft_data, num_harmonics=3,
    verbose=True, display=True):
    harmonic_pixels = []
    values = {}
    for v in fourier_lattice_vectors:
        harmonic_pixels.append([])
        for i in range(1, num_harmonics+1):
            harmonic_pixels[-1].append(tuple(numpy.round(i * v).astype(int)))
            values[harmonic_pixels[-1][-1]] = []

    for z in range(fft_data.shape[0]):
        for hp in harmonic_pixels:
            for p in hp:
                values[p].append(fft_data[z, p[0], p[1]])

    slopes = []
    for hp in harmonic_pixels:
        slopes.append(0)
        for n, p in enumerate(hp):
            values[p] = (1. / (n+1)) * numpy.unwrap(numpy.angle(values[p]))
            slopes[-1] += numpy.polyfit(range(len(values[p])), values[p], deg=1)[0]
        slopes[-1] *= 1. / len(hp)
    if verbose:
        for hp in harmonic_pixels:
            print hp
        print slopes

    if display:
        fig = pylab.figure()
        for n, hp in enumerate(harmonic_pixels):
            slope = slopes[n]
            for p in hp:
                plotMe = values[p] - slope * numpy.arange(len(values[p]))
                pylab.plot(plotMe - plotMe.mean(),
                           '.-', label=repr(p))
        pylab.grid()
        pylab.legend()
        pylab.ylabel('Deviation from expected phase')
        pylab.xlabel('Image number')
        pylab.title('This should look like noise')
        fig.show()

    x_s = numpy.zeros(2)
    num_vectors = 0
    for sl in (slice(0, 2), slice(0, 3, 2), slice(1, 3)):
        x_s += numpy.linalg.solve(
            (-2. * numpy.pi / numpy.array(fft_data.shape[1:])) *
            fourier_lattice_vectors[sl], slopes[sl])
        num_vectors += 1
    x_s *= 1.0 / num_vectors
    return x_s

def generate_lattice(
    image_shape, lattice_vectors, center_pix='image', edge_buffer=2):
    if center_pix == 'image':
        center_pix = numpy.array(image_shape) // 2
    num_vectors = max(
        [int(1.4*numpy.ceil(numpy.abs(center_pix * 1.0 / v).min()))
         for v in lattice_vectors])
    lattice_points = []
    lower_bounds = numpy.array((edge_buffer, edge_buffer))
    upper_bounds = numpy.array(image_shape) - edge_buffer
    for i in range(-num_vectors, num_vectors):
        for j in range(-num_vectors, num_vectors):
            lp = i * lattice_vectors[0] + j * lattice_vectors[1] + center_pix
            if all(lower_bounds < lp) and all(lp < upper_bounds):
                lattice_points.append(lp)
    return lattice_points

def get_offset_vector(
    first_image, direct_lattice_vectors,
    verbose=True, display=True, show_interpolation=True):
    if verbose: print "Calculating offset vector..."
    ws = 2 + 2*int(max(
        [abs(v).max() for v in direct_lattice_vectors])) #Window size
    if verbose: print "Window size:", ws
    window = numpy.zeros([ws]*2).astype(numpy.int64)
    lattice_points = generate_lattice(
        first_image.shape, direct_lattice_vectors, edge_buffer=2+ws)
    for lp in lattice_points:
        x, y = numpy.round(lp).astype(int)
        window += first_image[x:x+ws, y:y+ws]
    if display:
        fig = pylab.figure()
        pylab.imshow(window, interpolation='nearest', cmap=pylab.cm.gray)
        pylab.title('This should look like round blobs')
        fig.show()
    buffered_window = numpy.array(window)
    buffered_window[:2, :] = 0
    buffered_window[-2:, :] = 0
    buffered_window[:, :2] = 0
    buffered_window[:, -2:] = 0
    max_pix = numpy.unravel_index(buffered_window.argmax(), window.shape)
    if verbose: print max_pix
    correction = simple_max_finder(
        window[max_pix[0]-1:max_pix[0]+2, max_pix[1]-1:max_pix[1]+2],
        show_plots=show_interpolation)
    offset_vector = max_pix + correction + numpy.array(first_image.shape)//2
    return offset_vector

def get_lattice_vectors(
    filename='QDots.raw',
    xPix=512,
    yPix=512,
    zPix=201,
    extent=10,
    num_spikes=150,
    tilt_filter=True,
    tolerance=3.,
    num_harmonics=3,
    verbose=False,
    display=False,
    animate=False,
    show_interpolation=False,
    show_lattice=False):
    """Given the 2D ffts of an swept-field confocal image stack, finds
    the basis vectors of the illumination lattice pattern."""

    image_data = load_image_data(filename, xPix=xPix, yPix=yPix, zPix=zPix)
    fft_data, fft_abs = get_fft_abs(filename, image_data)
    fft_abs = numpy.fft.fftshift(fft_abs)
    
    coords = find_spikes(
        fft_abs, extent=extent, num_spikes=num_spikes, tilt_filter=tilt_filter,
        display=display, animate=animate)
    
    if verbose: print "Finding..."
    basis_vectors = get_basis_vectors(
        fft_abs, coords, extent=extent, tolerance=tolerance, verbose=verbose,
        show_interpolation=show_interpolation)

    if verbose:
        print "Fourier-space lattice vectors:"
        for v in basis_vectors:
            print v, "(Magnitude", numpy.sqrt((v**2).sum()), ")"

    error_vector = sum(basis_vectors)
    corrected_basis_vectors = [
        v - ((1./3.) * error_vector) for v in basis_vectors]
    if verbose:
        print "Fourier-space lattice vector triangle sum:", error_vector
        print "Corrected Fourier-space lattice vectors:"
        for v in corrected_basis_vectors:
            print v            
    
    area = numpy.cross(corrected_basis_vectors[0], corrected_basis_vectors[1])
    rotate_90 = ((0., -1.), (1., 0.))
    direct_lattice_vectors = [
        numpy.dot(v, rotate_90) * fft_abs.shape / area
        for v in corrected_basis_vectors]

    if verbose:
        print "Real-space lattice vectors:"
        for v in direct_lattice_vectors:
            print v
        print "Lattice vector triangle sum:", sum(direct_lattice_vectors)

    shift_vector = get_shift_vector(
        corrected_basis_vectors, fft_data, num_harmonics=num_harmonics,
        verbose=verbose, display=display)

    first_image = image_data[0, :, :]
    offset_vector = get_offset_vector(
        first_image, direct_lattice_vectors,
        verbose=verbose, display=display, show_interpolation=show_interpolation)

    if show_lattice:
        fig = pylab.figure()
        for s in range(image_data.shape[0]):
            pylab.clf()
            showMe = image_data[s, :, :]
            dots = numpy.zeros(list(showMe.shape) + [4])
            lattice_points = generate_lattice(
                showMe.shape, direct_lattice_vectors,
                center_pix=offset_vector + shift_vector * s)
            for lp in lattice_points:
                x, y = numpy.round(lp).astype(int)
                dots[x, y, 0::3] = 1
            pylab.imshow(showMe, cmap=pylab.cm.gray, interpolation='nearest')
            pylab.imshow(dots, interpolation='nearest')
            pylab.title("Red dots show the calculated illumination pattern")
            fig.show()
            fig.canvas.draw()
            raw_input('.')
            sys.stdout.write('\r%04i'%(s))
            sys.stdout.flush()
    

    return (corrected_basis_vectors, direct_lattice_vectors,
            shift_vector, offset_vector)
