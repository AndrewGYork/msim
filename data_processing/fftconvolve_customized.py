import numpy as np

def fftconvolve(
    in1,
    in2,
    mode="full",
    preprocessed_input=None
    ):
    """Convolve two N-dimensional arrays using FFT.

    Very similar to scipy.signal.fftconvolve, but with some performance 
    customizations to the padding, and optional preprocessing.

    scipy.signal.fftconvolve currently pads to a power of 2 for fast
    FFTs; this is often suboptimal, since numpy's FFTs are fast for
    array sizes that are products of small primes. Our version tries
    to guess a good padding size.

    Often, we find ourselves convolving many different in1's with the
    same in2. The 'preprocessed_input' argument lets us save
    computation time by passing a preprocessed version of in2.
    """
    in1 = np.asarray(in1)
    in2 = np.asarray(in2)

    if np.rank(in1) == np.rank(in2) == 0:  # scalar inputs
        return in1 * in2
    elif not in1.ndim == in2.ndim:
        raise ValueError("in1 and in2 should have the same rank")
    elif in1.size == 0 or in2.size == 0:  # empty arrays
        return array([])

    if preprocessed_input is None:
        preprocessed_input = preprocess_input_2(in1, in2)
    (in2_preprocessed,
     in2_preprocessed_is_complex,
     size,
     fsize,
     s1,
     s2
     ) = preprocessed_input

    complex_result = (np.issubdtype(in1.dtype, np.complex) or
                      in2_preprocessed_is_complex)

    fslice = tuple([slice(0, int(sz)) for sz in size])
    if not complex_result:
        ret = np.fft.irfftn(np.fft.rfftn(in1, fsize) * in2_preprocessed, fsize
                            )[fslice].copy()
        ret = ret.real
    else:
        ret = np.fft.ifftn(np.fft.fftn(in1, fsize) * in2_preprocessed
                           )[fslice].copy()

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

def preprocess_input_2(in1, in2):
    """
    Often, we call 'fftconvolve' many times with different 'in1' but
    the same 'in2'. In this case, it's a waste to spend 1/3 of the
    processing time computing the FFT of in2. This function computes
    this preprocessing just once.
    """
    in1 = np.asarray(in1)
    in2 = np.asarray(in2)

    s1 = np.array(in1.shape)
    s2 = np.array(in2.shape)
    complex_result = (np.issubdtype(in1.dtype, np.complex) or
                      np.issubdtype(in2.dtype, np.complex))
    size = s1 + s2 - 1
    #Pad to get better performance, but not necessarily to 2**n
    fsize = best_fft_shape(size)
    if complex_result:
        in2_preprocessed = np.fft.fftn(in2, fsize)
    else:
        in2_preprocessed = np.fft.rfftn(in2, fsize)
    
    return (in2_preprocessed, complex_result, size, fsize, s1, s2)

if __name__ == '__main__':
    import time, sys
    from scipy.signal import fftconvolve as fftconvolve_old

    if sys.platform == 'win32':
        clock = time.clock
    else:
        clock = time.time

    for s in range(50, 300):
        shape = (s, s)
        print shape
        a = np.arange(np.prod(shape), dtype=np.float64).reshape(shape)
        preprocessed_input = preprocess_input_2(a, a)

        start1 = clock()
        x = fftconvolve_old(a, a, mode='same')
        end1 = clock()

        start2 = clock()
        y = fftconvolve(a, a, mode='same')
        end2 = clock()

        start3 = clock()
        z = fftconvolve(
            a, a, mode='same', preprocessed_input=preprocessed_input)
        end3 = clock()

        if (np.abs(x - y).max() / y.mean() > 1e-10 or
            np.abs(x - z).max() / y.mean() > 1e-10):
            print 20*"*\n*"
            print "***WARNING: different answers!***"

        speedup_1 = (end1 - start1) / (end2 - start2 + 1e-9)
        speedup_2 = (end1 - start1) / (end3 - start3 + 1e-9)

        print "Speedup:", speedup_1
        print "Speedup:", speedup_2, "with preprocessing."
        if speedup_1 < 1:
            print "***NO SPEEDUP***"
            print
        if speedup_2 < speedup_1:
            print "***NO BENEFIT FROM PREPROCESSING***"
            print
