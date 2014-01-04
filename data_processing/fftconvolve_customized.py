import numpy as np

def fftconvolve(in1, in2, mode="full"):
    """Convolve two N-dimensional arrays using FFT.

    Very similar to scipy.signal.fftconvolve, but with some
    customizations to the padding.
    """
    in1 = np.asarray(in1)
    in2 = np.asarray(in2)

    if np.rank(in1) == np.rank(in2) == 0:  # scalar inputs
        return in1 * in2
    elif not in1.ndim == in2.ndim:
        raise ValueError("in1 and in2 should have the same rank")
    elif in1.size == 0 or in2.size == 0:  # empty arrays
        return array([])
    
    s1 = np.array(in1.shape)
    s2 = np.array(in2.shape)
    complex_result = (np.issubdtype(in1.dtype, np.complex) or
                      np.issubdtype(in2.dtype, np.complex))
    size = s1 + s2 - 1

    #Pad to get better performance, but not necessarily to 2**n
    fsize = best_fft_shape(s1+s2-1)
    fslice = tuple([slice(0, int(sz)) for sz in size])
    if not complex_result:
        ret = np.fft.irfftn(np.fft.rfftn(in1, fsize) *
                            np.fft.rfftn(in2, fsize), fsize)[fslice].copy()
        ret = ret.real
    else:
        ret = np.fft.ifftn(np.fft.fftn(in1, fsize) *
                           np.fft.fftn(in2, fsize))[fslice].copy()

    if mode == "full":
        return ret
    elif mode == "same":
        return _centered(ret, s1)
    elif mode == "valid":
        return _centered(ret, s1 - s2 + 1)

def _centered(arr, newsize):
    # Return the center newsize portion of the array.
    newsize = np.asarray(newsize)
    currsize = np.array(arr.shape)
    startind = (currsize - newsize) / 2
    endind = startind + newsize
    myslice = [slice(startind[k], endind[k]) for k in range(len(endind))]
    return arr[tuple(myslice)]

def factorize(n):
    if n == 0:
        raise(RuntimeError, "n must be positive integer")
    elif n == 1:
        return [1,]
    factors = []
    base = [13,11,7,5,3,2]
    for b in base:
        while n % b == 0:
            n /= b
            factors.append(b)
    if n == 1:
        return factors
    return []

def is_optimal(n):
    factors = factorize(n)
    return len(factors) > 0 \
        and factors[:2] not in [[13,13],[13,11],[11,11]]

def best_fft_shape(shape):
    """
    This function returns the best shape for computing a fft

    From fftw.org:
        FFTW is best at handling sizes of the form 2^a*3^b*5^c*7^d*11^e*13^f,
         where e+f is either 0 or 1,
    """
    shape = np.atleast_1d(np.array(shape))
    for i in range(shape.size):
        while not is_optimal(shape[i]):
            shape[i] += 1
    return shape.astype(int)

if __name__ == '__main__':
    import time
    from scipy.signal import fftconvolve as fftconvolve_old

    for s in range(50, 300):
        shape = (s, s)
        print shape
        a = np.arange(np.prod(shape), dtype=np.float64).reshape(shape)

        start1 = time.clock()
        x = fftconvolve_old(a, a, mode='same')
        end1 = time.clock()

        start2 = time.clock()
        y = fftconvolve(a, a, mode='same')
        end2 = time.clock()

        speedup = (end1 - start1) / (end2 - start2)

        print "Speedup:", speedup
        if speedup < 1:
            print "***NO SPEEDUP***"
            print
