import numpy
"""
I often save camera data as raw binary, since it's so easy. However,
this is annoying to load into ImageJ. For the fun of it, I decided to
learn how to write simple TIF files. Since I'm not dealing with the
overhead of the full TIF specification, this might actually be pretty
fast.
"""

"""
Each slice in the TIF has its own header. However, all these headers
are quite similar in my case, so I make a single header, and some
pointers to the spots in the header that change:
"""
header = numpy.fromstring(
    '\x0b\x00' + #Num tags = 11
    '\xfe\x00\x04\x00\x01\x00\x00\x00\x00\x00\x00\x00' + #Type
    '\x00\x01\x04\x00\x01\x00\x00\x00\x05\x00\x00\x00' + #Image width
    '\x01\x01\x04\x00\x01\x00\x00\x00\x07\x00\x00\x00' + #Image length
    '\x02\x01\x03\x00\x01\x00\x00\x00 \x00\x00\x00' + #Bits per sample
    '\x06\x01\x03\x00\x01\x00\x00\x00\x01\x00\x00\x00' + #Photometric gibberish
    '\x0e\x01\x02\x00;\x00\x00\x00\x92\x00\x00\x00' + #Im. descr. offset
    '\x11\x01\x04\x00\x01\x00\x00\x00\xcd\x00\x00\x00' + #Strip offsets
    '\x15\x01\x03\x00\x01\x00\x00\x00\x01\x00\x00\x00' + #Samples per pixel
    '\x16\x01\x03\x00\x01\x00\x00\x00\x07\x00\x00\x00' + #Rows per strip
    '\x17\x01\x04\x00\x01\x00\x00\x00\x8c\x00\x00\x00' + #Strip byte counts
    'S\x01\x03\x00\x01\x00\x00\x00\x01\x00\x00\x00' + #Image data format
    '\x15\x04\x00\x00', #Next IFD offset
    dtype=numpy.byte)
width = header[22:26].view(dtype=numpy.uint32)
length = header[34:38].view(dtype=numpy.uint32)
bits_per_sample = header[46:50].view(dtype=numpy.uint32)
num_chars_in_image_description = header[66:70].view(numpy.uint32)
strip_offset = header[82:86].view(numpy.uint32)
rows_per_strip = header[106:110].view(numpy.uint32)
strip_byte_counts = header[118:122].view(numpy.uint32)
data_format = header[130:134].view(numpy.uint32)
next_ifd_offset = header[134:138].view(numpy.uint32)

def array_to_tif(a, outfile='out.tif', slices=None, channels=None,
                 projected_preview_outfile=None):
    """
    'a' is assumed to be a 3D numpy array of 16-bit unsigned integers.
    I usually use this for stacks of camera data.
    If the data is multi-color, then slices * channels must equal a.shape[0].
    """
    assert len(a.shape) == 3
    z, y, x = a.shape
    if projected_preview_outfile is not None:
        """
        For viewers that don't like 3D data.
        """
        array_to_tif(a.max(axis=0).reshape(1, y, x),
                     outfile=projected_preview_outfile)
    if slices is not None and channels is not None:
        assert slices * channels == z
        hyperstack = True
    else:
        hyperstack = False
    """
    We have a precomputed header. We edit portions of the header which
    are specific to the array 'a':
    """
    width[0] = x
    length[0] = y
    allowed_dtypes = {
        numpy.dtype('uint8'): (1, 8),
        numpy.dtype('uint16'): (1, 16),
        numpy.dtype('uint32'): (1, 32),
        numpy.dtype('uint64'): (1, 64),
        numpy.dtype('int8'): (2, 8),
        numpy.dtype('int16'): (2, 16),
        numpy.dtype('int32'): (2, 32),
        numpy.dtype('int64'): (2, 64),
        ##numpy.dtype('float16'): (3, 16), #Not supported in older numpy?
        numpy.dtype('float32'): (3, 32),
        numpy.dtype('float64'): (3, 64),
        }
    try:
        data_format[0], bits_per_sample[0] = allowed_dtypes[a.dtype]
    except KeyError:
        warning_string = "Array datatype (%s) not allowed. Allowed types:"%(
            a.dtype)
        for i in sorted(allowed_dtypes.keys()):
            warning_string += '\n ' + repr(i)
        raise UserWarning(warning_string)
    if hyperstack:
        image_description = ''.join((
            'ImageJ=1.45s\nimages=%i\nchannels=%i\n'%(z, channels),
            'slices=%i\nhyperstack=true\nmode=grayscale\n'%(slices),
            'loop=false\nmin=%0.3f\nmax=%0.3f\n\x00'%(a.min(), a.max())))
    else:
        image_description = ''.join((
            'ImageJ=1.45s\nimages=%i\nslices=%i\n'%(z, z),
            'loop=false\nmin=%0.3f\nmax=%0.3f\n\x00'%(a.min(), a.max())))        
    num_chars_in_image_description[0] = len(image_description)
    strip_offset[0] = 8 + header.nbytes + len(image_description)
    rows_per_strip[0] = y
    strip_byte_counts[0] = x*y*bits_per_sample[0] // 8
    if z == 1:
        next_ifd_offset[0] = 0
    else:
        next_ifd_offset[0] = strip_offset[0] + a.nbytes

    f = open(outfile, 'wb')
    f.write('II*\x00\x08\x00\x00\x00')
    header.tofile(f)
    f.write(image_description)
    a.tofile(f)
    for which_header in range(1, z):
        if which_header == z-1:
            next_ifd_offset[0] = 0
        else:
            next_ifd_offset[0] += header.nbytes
        strip_offset[0] += strip_byte_counts[0]
        header.tofile(f)
    f.close()
    return None

"""
Now a simple parser, to check if our tif writer is doing what I hoped:
"""

def bytes_to_int(x):
    return sum(ord(c)*256**i for i, c in enumerate(x))

def parse_simple_tif(filename='out.tif'):
    f = open(filename, 'rb')
    t = f.read()
    f.close()
    assert t[0:4] == 'II*\x00' #Little Endian
    ifd_offset = bytes_to_int(t[4:8])
    assert ifd_offset == 8
    while True:
        num_tags = parse_simple_tags(t, ifd_offset)
        ifd_offset = bytes_to_int(t[ifd_offset + num_tags*12 + 2:
                                    ifd_offset + num_tags*12 + 6])
        print "Next IFD offset:",  ifd_offset #Pointer to next IFD
        print
        if ifd_offset == 0:
            break
    return None

def parse_simple_tags(t, ifd_offset, verbose=True):
    if verbose:
        print "IFD at offset", ifd_offset
    num_tags = bytes_to_int(t[ifd_offset:ifd_offset+2])
    assert num_tags == 10 #Ten tags
    for i in range(num_tags):
        tag = t[ifd_offset + 2 + 12*i:ifd_offset + 2 + 12*(i+1)]
        tag_code = bytes_to_int(tag[0:2])
        data_type = bytes_to_int(tag[2:4])
        num_values = bytes_to_int(tag[4:8])
        content = tag[8:]
        if verbose:
            print " Tag %02i:"%i, tag_code, 'dtype:', data_type,
            print 'num_values:', num_values, 'content:', repr(tag[8:])
        if i == 0:
            assert tag_code == 254
        elif i == 1:
            assert tag_code == 256
            if verbose:
                print "  Image width:", bytes_to_int(content)
        elif i == 2:
            assert tag_code == 257
            if verbose:
                print "  Image length:", bytes_to_int(content)
        elif i == 3:
            assert tag_code == 258
            if verbose:
                print "  Bits per sample:", bytes_to_int(content)
        elif i == 4:
            assert tag_code == 262
            assert bytes_to_int(content) == 1
            if verbose:
                print "  Photometric interpretation:", bytes_to_int(content)
        elif i == 5:
            assert tag_code == 270
            pointer = bytes_to_int(content)
            if verbose:
                print "  Image description offset:", pointer
                print "  Image description content:"
                print '  ' + repr(t[pointer:pointer+num_values])
        elif i == 6:
            assert tag_code == 273
            pointer = bytes_to_int(content)
            if verbose:
                print "  Strip offsets:", pointer
                print "  First five samples at this offset:"
                print '  ',
                for b in range(5):
                    print bytes_to_int(t[pointer+b*2:pointer+b*2+2]),
                print
        elif i == 7:
            assert tag_code == 277
            if verbose:
                print "  Samples per pixel:", bytes_to_int(content)
        elif i == 8:
            assert tag_code == 278
            if verbose:
                print "  Rows per strip:", bytes_to_int(content)
        elif i == 9:
            assert tag_code == 279
            if verbose:
                print "  Strip byte counts:", bytes_to_int(content)
    return num_tags

def simple_tif_to_array(filename='out.tif', verbose=True):
    """
    A very simple reader. Note that this is ONLY designed to read
    TIFs written by 'array_to_tif' in this module. Writing a general
    TIF reader is much more work.
    """
    with open(filename, 'rb') as f:
        if verbose:
            print "Reading header:", filename, "..."
        f.seek(8)
        f_header = f.read(len(header))
        if verbose:
            print " Done reading header."
        width = bytes_to_int(f_header[22:26])
        length = bytes_to_int(f_header[34:38])
        num_chars_in_image_description = bytes_to_int(f_header[66:70])
        if verbose:
            print "Reading image description:", filename, "..."
        image_description = f.read(num_chars_in_image_description).split()
        if verbose:
            print " Done reading image description."
        assert image_description[0] == 'ImageJ=1.45s'
        num_images = int(image_description[1].split('=')[1])
        if verbose:
            print " Width:", width
            print " Length:", length
            print " Num chars:", num_chars_in_image_description
            print " Image description:", image_description
            print " Num images:", num_images
        print "Reading data:", filename, "..."
        data = numpy.fromfile(
            f, dtype=numpy.uint16, count=width*length*num_images
            ).reshape(num_images, length, width)
        print " Done reading data."
    return data

def parse_tif(filename='out.tif'):
    f = open(filename, 'rb')
    t = f.read()
    f.close()
    assert t[0:4] == 'II*\x00' #Little Endian
    ifd_offset = bytes_to_int(t[4:8])
    while True:
        num_tags, ifd_info = parse_tags(t, ifd_offset, verbose=True)
        ifd_offset = bytes_to_int(t[ifd_offset + num_tags*12 + 2:
                                    ifd_offset + num_tags*12 + 6])
        print "Next IFD offset:",  ifd_offset #Pointer to next IFD
        print
        if ifd_offset == 0:
            break
    return None

def parse_tags(t, ifd_offset, verbose=True):
    if verbose:
        print "IFD at offset", ifd_offset
    num_tags = bytes_to_int(t[ifd_offset:ifd_offset+2])
    if verbose:
        print "Full IFD:\n", repr(t[ifd_offset:ifd_offset + 6 + 12*num_tags])
        print
    dtype = 'uint'
    for i in range(num_tags):
        tag = t[ifd_offset + 2 + 12*i:ifd_offset + 2 + 12*(i+1)]
        if verbose:
            print repr(tag)
        tag_code = bytes_to_int(tag[0:2])
        data_type = bytes_to_int(tag[2:4])
        num_values = bytes_to_int(tag[4:8])
        content = tag[8:]
        if verbose:
            print " Tag %02i:"%i, tag_code, 'dtype:', data_type,
            print 'num_values:', num_values, 'content:', repr(tag[8:])
        if tag_code == 256:
            image_width = bytes_to_int(content)
            if verbose:
                print "  Image width:", image_width
        elif tag_code == 257:
            image_length = bytes_to_int(content)
            if verbose:
                print "  Image length:", image_length
        elif tag_code == 258:
            bits_per_sample = bytes_to_int(content)
            assert bits_per_sample in (8, 16, 32, 64)
            if verbose:
                print "  Bits per sample:", bits_per_sample
        elif tag_code == 270:
            image_description_pointer = bytes_to_int(content)
            image_description = t[image_description_pointer:
                                  image_description_pointer+num_values]
            if verbose:
                print "  Image description offset:", image_description_pointer
                print "  Image description content:"
                print '  ' + repr(image_description)
        elif tag_code == 273:
            data_pointer = bytes_to_int(content)
            if verbose:
                print "  Num values:", num_values
            assert num_values == 1
            if verbose:
                print "  Strip offsets:", data_pointer
                print "  First five samples at this offset:"
                print '  ',
                for b in range(5):
                    print bytes_to_int(t[data_pointer+b*2:data_pointer+b*2+2]),
                print
        elif tag_code == 278:
            rows_per_strip = bytes_to_int(content)
            if verbose:
                print "  Rows per strip:", rows_per_strip
        elif tag_code == 279:
            strip_byte_counts = bytes_to_int(content)
            if verbose:
                print "Num values:", num_values
            assert num_values == 1
            if verbose:
                print "  Strip byte counts:", strip_byte_counts
        elif tag_code == 339:
            dtype = {
                1: 'uint',
                2: 'int',
                3: 'float',
                4: 'undefined',
                }[bytes_to_int(content)]
            if verbose:
                print "Image data type:", dtype
    ifd_info = {
        'num_tags': num_tags,
        'width': image_width,
        'length': image_length,
        'bit_depth': bits_per_sample,
        'description': image_description,
        'strip_offset': data_pointer,
        'rows_per_strip': rows_per_strip,
        'strip_byte_count': strip_byte_counts,
        'format': dtype,
        }
    return num_tags, ifd_info

def tif_to_array(filename='out.tif', verbose=False, return_info=False):
    """
    A very simple reader. Note that this is ONLY designed to read
    TIFs written by 'array_to_tif' in this module. Writing a general
    TIF reader is much harder.
    """
    f = open(filename, 'rb')
    t = f.read()
    f.close()
    strip_offsets = []
    strip_byte_counts = []
    assert t[0:4] == 'II*\x00' #Little Endian
    ifd_offset = bytes_to_int(t[4:8])
    while True:
        num_tags, ifd_info = parse_tags(t, ifd_offset, verbose=verbose)
        strip_offsets.append(ifd_info['strip_offset'])
        strip_byte_counts.append(ifd_info['strip_byte_count'])
        ifd_offset = bytes_to_int(t[ifd_offset + ifd_info['num_tags']*12 + 2:
                                    ifd_offset + ifd_info['num_tags']*12 + 6])
        if verbose:
            print "Next IFD offset:",  ifd_offset #Pointer to next IFD
            print
        if ifd_offset == 0:
            break
    gaps = numpy.diff(strip_offsets) - numpy.array(strip_byte_counts)[:-1]
    if len(gaps) == 0: #Only one slice
        continuous = True
    elif gaps.max() == 0 and gaps.min() == 0:
        continuous = True
    if continuous:
        """ The data is stored in one continuous array, in the order
        we expect. Load it like a raw binary file. """
        data_length = numpy.sum(strip_byte_counts)
        data_format = ifd_info['format']
        data_bitdepth = ifd_info['bit_depth']
        data_type = data_format + str(data_bitdepth)
        try:
            data_type = getattr(numpy, data_type)
        except AttributeError:
            raise UserWarning("Unsupported data format: " + data_type)
        data = numpy.fromstring(t[strip_offsets[0]:
                                  strip_offsets[0] + data_length],
                                dtype=data_type)
    else:
        raise UserWarning("The data is not written as one continuous block")
    num_slices = data.size // (ifd_info['length'] * ifd_info['width'])
    if return_info:
        return (data.reshape(num_slices, ifd_info['length'], ifd_info['width']),
                ifd_info)
    else:
        return data.reshape(num_slices, ifd_info['length'], ifd_info['width'])

if __name__ == '__main__':
    a = numpy.arange(7*800*900, dtype=numpy.float64).reshape(7, 800, 900)
    array_to_tif(a)
##    parse_tif()
    b = tif_to_array(verbose=False)
    print b.dtype, b.shape
    assert a[3, 5, 19] == b[3, 5, 19]
    print "Biggest difference:", abs(a - b).max()

    a = numpy.arange(6*800*900, dtype=numpy.float64).reshape(6, 800, 900)
    array_to_tif(a, slices=2, channels=3)
##    parse_tif()
    b, info = tif_to_array(verbose=False, return_info=True)
    print b.dtype, b.shape
    print info
    assert a[3, 5, 19] == b[3, 5, 19]
    print "Biggest difference:", abs(a - b).max()


