import os, sys, time, ConfigParser
import numpy
import Tkinter as Tk, tkFileDialog, tkSimpleDialog
from scipy.ndimage import gaussian_filter, center_of_mass
from scipy.fftpack import fftn, ifftn, fftshift
from simple_tif import tif_to_array, array_to_tif

if sys.platform.startswith('win'):
    clock = time.clock
else:
    clock = time.time

def richardson_lucy_deconvolution(
    image_data=None,
    psf_data=None,
    num_iterations=None,
    modify_psf=False,
    image_data_shape=None,
    image_data_dtype=None,
    psf_data_shape=None,
    psf_data_dtype=None,
    psf_sigma=None,
    verbose=True,
    ):
    """Deconvolve a 2D or 3D image using the Richardson-Lucy algorithm
    from an image and a point-spread funciton (PSF)

    'image_data': a numpy array, a filename, or None to have the user
    select a file with a graphical interface. If a filename, 
    
    'psf_type': 'gaussian', a numpy array, a filename, or None to have
    the user select a PSF data file using the graphical interface.

    num_iterations: The number of times to iteratively refine the
    object estimate.

    modify_psf: Boolean. If True, then both the PSF and the image data
    are modified on every iteration. If false, then tne PSF is assumed
    to be exact, and only the image data is modified.
    """

    """
    Select and load image data.
    """

    config = get_config()
    image_data = image_data_as_array(
        image_data, image_data_shape, image_data_dtype, verbose, config)
    if image_data == 'cancelled':
        print "Deconvolution cancelled.\n"
        return None
    else:
        image_data = image_data.astype(numpy.float64)

    if psf_data is None:
        psf_data = ask_psf_type(config)
        if psf_data == 'cancelled':
            print "Deconvolution cancelled.\n"
            return None

    if psf_data == 'gaussian':
        if psf_sigma is None:
            psf_sigma = ask_psf_sigma(config)
        else:
            assert len(psf_sigma) == len(image_data.shape)
            for s in psf_sigma:
                try:
                    assert float(s) == s
                except(AssertionError, ValueError):
                    print "psf_sigma:", psf_sigma
                    raise UserWarning(
                        "'psf_sigma' must be either None or a tuple of" +
                        " numbers with one entry for each dimension" +
                        " of the input image.")
    else:
        psf_data = image_data_as_array(
            psf_data, psf_data_shape, psf_data_dtype, verbose, config,
            title='Select a PSF file', initialfile='psf.tif')
        if psf_data == 'cancelled':
            print "Deconvolution cancelled\n"
            return None
        else:
            psf_data = psf_data.astype(numpy.float64)
        psf_data = condition_psf_data(
            psf_data, new_shape=image_data.shape)

    if num_iterations is None:
        try:
            initial_value = int(config.get('File', 'last_num_iterations'))
        except:
            initial_value = 10
        root = Tk.Tk()
        root.withdraw()
        num_iterations = tkSimpleDialog.askinteger(
            title="Iterations",
            prompt="How many deconvolution iterations?",
            initialvalue=initial_value,
            minvalue=1)
        root.destroy()
        if num_iterations is None:
            print "Deconvolution cancelled\n"
            return None
        config.set('File', 'last_num_iterations')
        save_config(config)
        "Number of iterations to perform:", num_iterations

    estimate = image_data.copy()
    history = numpy.zeros((num_iterations + 1,) + (image_data.shape[1:]))
    history[0, :, :] = estimate.max(axis=0) / estimate.max(axis=0).mean()

    if psf_data != 'gaussian':
        print "Precomputing..."
        start = clock()
        psf_data_fft = fftn(psf_data)
        psf_data_fft_r = psf_data_fft[::-1, ::-1, ::-1]
        end = clock()
        print "Done precomputing. Time:", end - start

    for i in range(num_iterations):
        print "Computing iteration %i..."%i
        start = clock()
        if psf_data == 'gaussian':
            blurred_estimate = gaussian_filter(estimate, sigma=psf_sigma)
            estimate *= gaussian_filter((image_data /
                                         blurred_estimate), sigma=psf_sigma)
        else:
            blurred_estimate = ifftn(psf_data_fft * fftn(estimate)).real
            estimate *= ifftn(psf_data_fft_r * fftn(image_data /
                                                    blurred_estimate)
                              ).real
        end = clock()
        print " Time:", end - start
        print " Done computing."
        print "Saving..."
        estimate.tofile('estimate.raw')
        history[i+1, :, :] = estimate.max(axis=0) / (
            estimate.max(axis=0).mean())
        history.tofile('history.raw')
        print "Done saving."
    return (estimate, history)

def condition_psf_data(psf_data, new_shape=None):
    """Prepare the PSF for FFT-based convolution.
    Subtract background
    Normalize
    Center
    Pad to the same size as the image data.
    """
    assert type(psf_data) is numpy.ndarray
    if new_shape is None:
        new_shape = psf_data.shape
    psf_data -= (1 - 1e-3) * psf_data.min()
    psf_data /= psf_data.sum()
    psf_brightest_pixel = numpy.unravel_index(
        gaussian_filter(psf_data, sigma=2).argmax(),
        dims=psf_data.shape)
    for i, shift in enumerate(psf_brightest_pixel):
        psf_data = numpy.roll(psf_data, psf_data.shape[i]//2 - shift, axis=i)
    for i in range(len(psf_data.shape)):
        if new_shape[i] < psf_data.shape[i]:
            slices = [slice(0, s) for s in psf_data.shape]
            low_crop = (psf_data.shape[i] - new_shape[i]) // 2
            high_crop = (psf_data.shape[i] - new_shape[i]) - low_crop
            slices[i] = slice(low_crop, -high_crop)
            psf_data = psf_data[slices]
    padded_psf_data = numpy.zeros(new_shape, dtype=numpy.float64)
    slices = []
    for i, s in enumerate(new_shape):
        low_crop = s//2 - psf_data.shape[i]//2
        high_crop = low_crop + psf_data.shape[i]
        slices.append(slice(low_crop, high_crop))
    padded_psf_data[slices] = psf_data
##    import pylab
##    print psf_data.shape
##    print padded_psf_data.shape
##    if display:
##        fig = pylab.figure()
##        pylab.imshow(padded_psf_data.sum(axis=0),
##                     cmap=pylab.cm.gray, interpolation='nearest')
##        fig.show()
##    padded_psf_data.tofile('out.raw')
    return fftshift(padded_psf_data)

def image_data_as_array(
    image_data, image_data_shape, image_data_dtype,
    verbose, config,
    title='Select an image to deconvolve',
    initialfile='image.tif',
    ):

    if image_data is None:
        root = Tk.Tk()
        root.withdraw()
        image_data = str(os.path.normpath(tkFileDialog.askopenfilename(
            title=title,
            filetypes=[('TIFF or raw binary', '.tif'),
                       ('TIFF or raw binary', '.raw'),
                       ('TIFF or raw binary', '.tiff'),
                       ('TIFF or raw binary', '.dat')],
            defaultextension='.tif',
            initialdir=os.getcwd(),
            initialfile=initialfile,
            )))
        root.destroy()
        if image_data == '.':
            return 'cancelled'

    if type(image_data) is str:
        while True:
            try:
                image_data = image_filename_to_array(
                    image_data,
                    shape=image_data_shape,
                    dtype=image_data_dtype,
                    verbose=verbose,
                    config=config)
                break
            except UserWarning as e:
                print e
        if image_data == 'cancelled':
            return 'cancelled'
    print image_data.shape
    assert type(image_data) is numpy.ndarray
    return image_data

def image_filename_to_array(
    image_filename, shape=None, dtype=None, verbose=True, config=None):
    """Load tif (.tif, .tiff extension) and raw binary files (.dat,
    .raw extension). If raw binary, 'dtype' and 'shape' must be specified."""
    if verbose:
        print "Loading %s..."%(os.path.split(image_filename)[1])
    extension = os.path.splitext(image_filename)[1]
    if extension in ('.tif', '.tiff'):
        return tif_to_array(image_filename)
    elif extension in ('.raw', '.dat'):
        if (shape is None) or (dtype is None):
            info = get_image_info(image_filename, config=config)
            if info == 'cancelled':
                return 'cancelled'
            xy_shape, dtype_name = info
            config.set('File', 'last_leftright_shape', repr(xy_shape[1]))
            config.set('File', 'last_updown_shape', repr(xy_shape[0]))
            config.set('File', 'last_dtype', dtype_name)
            save_config(config)
            dtype = {
                'uint8': numpy.uint8,
                'uint16': numpy.uint16,
                'uint32': numpy.uint32,
                'float32': numpy.float32,
                'float64': numpy.float64,
                }[dtype_name]
        else:
            xy_shape = shape[1:]
        data = numpy.fromfile(image_filename, dtype=dtype)
        try:
            data = data.reshape(
                (data.size // (xy_shape[0] * xy_shape[1]),) + xy_shape)
        except ValueError:
            raise UserWarning("The given shape and datatype do not match" +
                              " the size of %s"%(
                                  os.path.split(image_filename)[1]))
        return data
    else:
        raise UserWarning("Extension '%s' not recognized.\n"%(extension) +
                          "File extension must be one of:\n"
                          " ('.tif', '.tiff', '.raw', '.dat').")

def get_image_info(image_filename, config=None):
    try:
        initial_shape = (
            config.get('File', 'last_updown_shape'),
            config.get('File', 'last_leftright_shape'))
        initial_dtype = config.get('File', 'last_dtype')
    except:
        print "Error loading config file"
        initial_shape = ('0', '0')
        initial_dtype='uint16'
    d = ImageInfoDialog(
        image_filename=image_filename,
        initial_shape=initial_shape,
        initial_dtype=initial_dtype)
    if not d.validated:
        return 'cancelled'
    xy_shape, dtype = d.shape, d.dtype_name.get()
    return xy_shape, dtype

class ImageInfoDialog:
    def __init__(self, image_filename, master=None,
                 initial_shape=('0', '0'), initial_dtype='uint16'):
        if master is None:
            self.master = Tk.Tk()
            self.master.withdraw()
            master_existed = False
        else:
            self.master=master
            master_existed = True

        self.validated = False

        self.root = Tk.Toplevel(master=self.master)
        self.root.wm_title('Info')
        self.root.bind("<Escape>", lambda x: self.root.destroy())

        a = Tk.Label(text=os.path.split(image_filename)[1], master=self.root)
        a.pack()
        a = Tk.Label(text='Dimensions:', master=self.root)
        a.pack()

        a = Tk.Label(text=' Left-right:', master=self.root)
        a.pack()
        self.lr_pixels = Tk.StringVar()
        a = Tk.Spinbox(values=range(1, int(1e5)), increment=1,
                       textvar=self.lr_pixels, master=self.root)
        a.focus_set()
        a.bind("<Return>", self.validate)
        self.lr_pixels.set(initial_shape[1])
        a.pack()

        a = Tk.Label(text=' Up-down:', master=self.root)
        a.pack()
        self.ud_pixels = Tk.StringVar()
        a = Tk.Spinbox(values=range(1, int(1e5)), increment=1,
                       textvar=self.ud_pixels, master=self.root)
        a.bind("<Return>", self.validate)
        self.ud_pixels.set(initial_shape[0])
        a.pack()
        
        a = Tk.Label(text=' Data type:', master=self.root)
        a.pack()
        self.dtype_names = (
            'uint8',
            'uint16',
            'uint32',
            'float32',
            'float64',
            )
        self.dtype_name = Tk.StringVar()
        self.dtype_name.set(initial_dtype)
        a = Tk.OptionMenu(self.root, self.dtype_name, *self.dtype_names)
        a.bind("<Return>", self.validate)
        a.pack()

        a = Tk.Button(text='Ok', master=self.root, command=self.validate)
        a.pack()
        
        a = Tk.Button(text='Cancel', master=self.root,
                      command=self.root.destroy)
        a.pack()

        self.master.wait_window(self.root)
        if not master_existed:
            self.master.destroy()

    def validate(self, event=None):
        try:
            self.shape = (
                int(self.ud_pixels.get()),
                int(self.lr_pixels.get()),
                )
        except ValueError:
            print 'Invalid data shape'
            return None
        try:
            assert self.dtype_name.get() in self.dtype_names
        except KeyError:
            print "Invalid data type"
            return None
        try:
            for s in self.shape:
                assert s > 0
        except AssertionError:
            print 'Invalid data shape'
            return None
        """If we got this far, things are good!"""
        self.root.destroy()
        self.validated = True
        return None

def ask_psf_type(config=None):
    try:
        initial_type = config.get('File', 'last_psf_type')
    except:
        print "Failed to load PSF type from config file"
        initial_type = 'gaussian'
    d = PsfTypeDialog(initial_type=initial_type)
    if not d.validated:
        return 'cancelled'
    config.set('File', 'last_psf_type', d.psf_type)
    save_config(config)
    if d.psf_type == 'User-supplied TIFF or RAW':
        return None
    return d.psf_type

class PsfTypeDialog:
    def __init__(self, initial_type, master=None):
        if master is None:
            self.master = Tk.Tk()
            self.master.withdraw()
            master_existed = False
        else:
            self.master=master
            master_existed = True

        self.validated = False

        self.root = Tk.Toplevel(master=self.master)
        self.root.wm_title('PSF type')
        self.root.bind("<Escape>", lambda x: self.root.destroy())

        a = Tk.Label(text='Point spread function type:', master=self.root)
        a.pack()
        self.psf_types = (
            'gaussian',
            'User-supplied TIFF or RAW'
            )
        self.psf_type = Tk.StringVar()
        self.psf_type.set(initial_type)
        a = Tk.OptionMenu(self.root, self.psf_type, *self.psf_types)
        a.bind("<Return>", self.validate)
        a.pack()

        a = Tk.Button(text='Ok', master=self.root, command=self.validate)
        a.bind("<Return>", self.validate)
        a.pack()
        a.focus_set()
        
        a = Tk.Button(text='Cancel', master=self.root,
                      command=self.root.destroy)
        a.pack()

        self.master.wait_window(self.root)
        if not master_existed:
            self.master.destroy()

    def validate(self, event=None):
        try:
            assert self.psf_type.get() in self.psf_types
        except KeyError:
            print "Invalid psf type"
            return None
        """If we got this far, things are good!"""
        self.root.destroy()
        self.validated = True
        self.psf_type = self.psf_type.get()
        return None

def ask_psf_sigma(config=None):
    try:
        initial_fwhm = (
            config.get('File', 'last_axial_psf_fwhm'),
            config.get('File', 'last_updown_psf_fwhm'),
            config.get('File', 'last_leftright_psf_fwhm'))
    except:
        print "Error loading PSF FWHM from config file"
        initial_fwhm = ('1', '1', '1')
    d = PsfFwhmDialog(initial_fwhm=initial_fwhm)
    if not d.validated:
        return 'cancelled'
    config.set('File', 'last_axial_psf_fwhm', repr(d.fwhm[0]))
    config.set('File', 'last_updown_psf_fwhm', repr(d.fwhm[1]))
    config.set('File', 'last_leftright_psf_fwhm', repr(d.fwhm[2]))
    save_config(config)
    conversion = 1.0 / (2*numpy.sqrt(2*numpy.log(2)))
    sigma = [conversion * f for f in d.fwhm]
    return sigma

class PsfFwhmDialog:
    def __init__(self, initial_fwhm, master=None):
        if master is None:
            self.master = Tk.Tk()
            self.master.withdraw()
            master_existed = False
        else:
            self.master=master
            master_existed = True

        self.validated = False

        self.root = Tk.Toplevel(master=self.master)
        self.root.wm_title('PSF info')
        self.root.bind("<Escape>", lambda x: self.root.destroy())

        a = Tk.Label(text='Dimensions (FWHM in pixels):', master=self.root)
        a.pack()

        a = Tk.Label(text=' Left-right:', master=self.root)
        a.pack()
        self.lr_pixels = Tk.StringVar()
        a = Tk.Spinbox(values=range(1, int(1e5)), increment=1,
                       textvar=self.lr_pixels, master=self.root)
        a.focus_set()
        a.bind("<Return>", self.validate)
        self.lr_pixels.set(initial_fwhm[2])
        a.pack()

        a = Tk.Label(text=' Up-down:', master=self.root)
        a.pack()
        self.ud_pixels = Tk.StringVar()
        a = Tk.Spinbox(values=range(1, int(1e5)), increment=1,
                       textvar=self.ud_pixels, master=self.root)
        a.bind("<Return>", self.validate)
        self.ud_pixels.set(initial_fwhm[1])
        a.pack()
        
        a = Tk.Label(text=' Axial:', master=self.root)
        a.pack()
        self.axial_pixels = Tk.StringVar()
        a = Tk.Spinbox(values=range(1, int(1e5)), increment=1,
                       textvar=self.axial_pixels, master=self.root)
        a.bind("<Return>", self.validate)
        self.axial_pixels.set(initial_fwhm[0])
        a.pack()

        a = Tk.Button(text='Ok', master=self.root, command=self.validate)
        a.pack()
        
        a = Tk.Button(text='Cancel', master=self.root,
                      command=self.root.destroy)
        a.pack()

        self.master.wait_window(self.root)
        if not master_existed:
            self.master.destroy()

    def validate(self, event=None):
        try:
            self.fwhm = (
                float(self.axial_pixels.get()),
                float(self.ud_pixels.get()),
                float(self.lr_pixels.get()),
                )
        except ValueError:
            print 'Invalid PSF dimensions'
            return None
        try:
            for s in self.fwhm:
                assert s > 0
        except AssertionError:
            print 'Invalid PSF dimensions'
            return None
        """If we got this far, things are good!"""
        self.root.destroy()
        self.validated = True
        return None

def get_config():
    filename = os.path.join(os.getcwd(), 'decon_config.ini')
    config = ConfigParser.RawConfigParser()
    config.read(filename)
    for section, option, default in (
        ('File', 'last_leftright_shape', '0'),
        ('File', 'last_updown_shape', '0'),
        ('File', 'last_dtype', 'uint16')
        ):
        while True:
            try:
                config.get(section, option)
            except ConfigParser.NoSectionError:
                config.add_section(section)
            except ConfigParser.NoOptionError:
                config.set(section, option, default)
            break
    save_config(config)
    return config

def save_config(config):
    with open(os.path.join(os.getcwd(), 'decon_config.ini'), 'wb'
              ) as configfile:
        config.write(configfile)
    return None

if __name__ == '__main__':
##    richardson_lucy_deconvolution(image_data='200nm_steps_cropped.tif',
##                                  psf_data='gaussian')

##    richardson_lucy_deconvolution(
##        image_data='200nm_steps_cropped.raw',
##        image_data_shape=(51, 406, 487),
##        image_data_dtype=numpy.uint16)
##
##    richardson_lucy_deconvolution(image_data='200nm_steps_cropped.raw')
##
    richardson_lucy_deconvolution()
 
