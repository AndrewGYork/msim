import numpy
"""
I often save camera data as raw binary, since it's so easy. However,
this is annoying to load into ImageJ. For the fun of it, I decided to
learn how to write simple TIFF files. Since I'm not dealing with the
overhead of the full TIFF specification, this might actually be pretty
fast.
"""

"""
Each slice in the TIFF has its own header. However, all these headers
are quite similar in my case, so I make a single header, and some
pointers to the spots in the header that change:
"""
header = numpy.fromstring('\n\x00\xfe\x00\x04\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x04\x00\x01\x00\x00\x00\x02\x00\x00\x00\x01\x01\x04\x00\x01\x00\x00\x00\x05\x00\x00\x00\x02\x01\x03\x00\x01\x00\x00\x00\x10\x00\x00\x00\x06\x01\x03\x00\x01\x00\x00\x00\x01\x00\x00\x00\x0e\x01\x02\x00?\x00\x00\x00\x86\x00\x00\x00\x11\x01\x04\x00\x01\x00\x00\x00\xc5\x00\x00\x00\x15\x01\x03\x00\x01\x00\x00\x00\x01\x00\x00\x00\x16\x01\x03\x00\x01\x00\x00\x00\x05\x00\x00\x00\x17\x01\x04\x00\x01\x00\x00\x00\x14\x00\x00\x00\x01\x00\x00\x00', dtype=numpy.byte)
width = header[22:26].view(dtype=numpy.uint32)
length = header[34:38].view(dtype=numpy.uint32)
num_chars_in_image_description = header[66:70].view(numpy.uint32)
strip_offset = header[82:86].view(numpy.uint32)
rows_per_strip = header[106:110].view(numpy.uint32)
strip_byte_counts = header[118:122].view(numpy.uint32)
next_ifd_offset = header[122:126].view(numpy.uint32)

def array_to_tiff(a, outfile='out.tif'):
    """
    'a' is assumed to be a 3D numpy array of 16-bit unsigned integers.
    I usually use this for stacks of camera data.
    """
    assert a.dtype == numpy.uint16
    assert len(a.shape) == 3
    z, y, x = a.shape
    """
    We have a precomputed header. We edit portions of the header which
    are specific to the array 'a':
    """
    width[0] = x
    length[0] = y
    image_description = ''.join((
        'ImageJ=1.45s\nimages=%i\nslices=%i\n'%(z, z),
        'loop=false\nmin=%0.3f\nmax=%0.3f\n\x00'%(a.min(), a.max())))
    num_chars_in_image_description[0] = len(image_description)
    strip_offset[0] = 8 + header.nbytes + len(image_description)
    rows_per_strip[0] = y
    strip_byte_counts[0] = x*y*2
    if z == 1:
        next_ifd_offset[0] = 0
    else:
        next_ifd_offset[0] = strip_offset[0] + a.nbytes

    f = open(outfile, 'wb')
    f.write('II*\x00\x08\x00\x00\x00')
    header.tofile(f)
    f.write(image_description)
    a.tofile(f)
    for which_header in range(2, z):
        if which_header == z-1:
            next_ifd_offset[0] = 0
        else:
            next_ifd_offset[0] += header.nbytes
        strip_offset[0] += strip_byte_counts[0]
        header.tofile(f)
    f.close()
    return None

"""
Now a simple parser, to check if our tiff writer is doing what I hoped:
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

def simple_tif_to_array(filename='out.tif', out=None, verbose=True):
    """
    A very simple reader. Note that this is ONLY designed to read
    TIFFs written by 'array_to_tif' in this module. Writing a general
    TIFF reader is much harder.
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


if __name__ == '__main__':
    a = numpy.arange(7*800*900, dtype=numpy.uint16).reshape(7, 800, 900)
    print "Number of bytes:", a[0, :, :].nbytes
    array_to_tiff(a)
    parse_simple_tif()
    b = simple_tif_to_array()
    assert a[3, 5, 19] == b[3, 5, 19]         
