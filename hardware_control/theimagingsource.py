import ctypes as C
import os
import time
import numpy as np
import simple_tif

class DMK_23GP031:
    def __init__(self, verbose=True):
        """
        Find the camera
        """
        num_devices = dll.get_device_count()
        for d in range(num_devices):
            name = dll.get_unique_name_from_list(d)
            if len(name) > 0:
                if name.split()[0] == 'DMK' and name.split()[1] == '23GP031':
                    if verbose:
                        print "DMK camera found with serial number:",
                        print name.split()[2]
                    break
        else:
            raise UserWarning("Failed to find a DMK 23GP031 camera.\n" +
                              "Is the camera plugged in?")
        self.name = name
        """
        Take custody of the camera
        """
        self.handle = dll.create_grabber()
        if verbose: print "Opening camera", self.name, "...",
        assert dll.open_by_name(self.handle, self.name) == dll.success
        assert dll.is_valid(self.handle) == dll.success
        if verbose: print "camera open."
##        """
##        Reset everything to default values - why doesn't this work?
##        """
##        result = dll.reset_to_default(self.handle)
##        print "Reset:", result
##        assert result == 1
        """
        Figure out what video formats are supported, and set a default
        """
        num_formats = dll.get_video_format_count(self.handle)
        self.video_formats = []
        for f in range(num_formats):
            fmt = dll.get_video_format(self.handle, f)
            self.video_formats.append(fmt)
        self.set_video_format(self.video_formats[0], verbose=verbose)

        self.set_exposure(0.1)
        self.enable_trigger(0) 
        return None

    def set_video_format(self, video_format, verbose=True):
        """
        For now, we'll only deal with 16-bit format.
        """
        assert video_format.startswith("Y16")
        if verbose: print "Setting video format:",
        if video_format in self.video_formats:
            result = dll.set_video_format(self.handle, video_format)
            assert result == dll.success
            if verbose: print video_format
        else:
            print "Error."
            print "Available formats:"
            for f in self.video_formats:
                print repr(f)
            print "Requested format (", video_format, ") not available"
            raise UserWarning("Requested format not available")
        """
        After setting the video format, we need to make sure the sink
        format is set the same. We also need to call start_live at
        least once, so that get_format and get_image_information can
        be called; the call to set_sink_format will take care of this.
        """
        self.set_sink_format(verbose=verbose)
        """
        Finally, we should check that our changes to the video and
        sink format were successful, and update the corresponding
        attributes.
        """
        self.get_image_information(verbose=verbose)
        return None

    def set_sink_format(self, verbose=True):
        """
        For now, just set the "sink format" to Y16
        """
        if verbose: print "Setting sink format:",
        """
        First, you have to remove the overlay. I don't know what that
        is, but it's required for Y16 operation. This is not yet well
        documented, but if you read tisgrabber.h, you see this
        mentioned.
        """
        assert dll.remove_overlay(self.handle, 0) == dll.success
        """
        You can only set the sink format when the camera is not live, I think.
        """
        assert dll.set_format(self.handle, dll.Y16) == dll.success
        """
        However, you cannot call get_format until the camera has started live!
        """
        live = dll.start_live(self.handle, 0)
        if live != 1:
            print "Live:", live
            raise UserWarning(
                "TIS camera failed to start." +
                " Is another program controlling the camera?")
        assert dll.stop_live(self.handle) == dll.success
        assert dll.get_format(self.handle) == dll.Y16
        if verbose: print "Y16"
        return None        

    def get_image_information(self, verbose=True):
        if verbose: print "Image information:",
        width, height = C.c_long(777), C.c_long(777)
        bits, fmt = C.c_int(777), C.c_int(777)
        assert dll.get_image_description(self.handle,
                                         width,
                                         height,
                                         bits,
                                         fmt) == dll.success
        self.width = int(width.value)
        self.height = int(height.value)
        self.bit_depth = int(bits.value)
        self.sink_format = int(fmt.value)
        if verbose:
            print self.width, self.height, self.bit_depth, self.sink_format
        return None

    def set_exposure(self, exposure_seconds, verbose=True):
        """
        Make sure autoexposure is disabled
        """
        autoexposure = C.c_int(777)
        result = dll.get_auto_property(self.handle, dll.exposure, autoexposure)
        assert result == dll.success
        if autoexposure.value != 0:
            if verbose: print "Deactivating autoexposure...",
            result = dll.set_auto_property(self.handle, dll.exposure, 0)
            assert result == dll.success
            result = dll.get_auto_property(
                self.handle, dll.exposure, autoexposure)
            assert result == 1
            assert autoexposure.value == 0
            if verbose: print "done."
        """
        Get the min and max allowed values
        """
        min_exp, max_exp = C.c_long(777), C.c_long(778)
        result = dll.get_property_range(
            self.handle, dll.exposure, min_exp, max_exp)
        assert result == dll.success
        """
        Check that the requested value is sane
        """
        exposure_microseconds = int(exposure_seconds * 1e6)
        if not (min_exp.value < exposure_microseconds < max_exp.value):
            print "Minimum exposure:", min_exp.value * 1e-6, "(s)"
            print "Maximum exposure:", max_exp.value * 1e-6, "(s)"
            raise UserWarning("Requested exposure is not possible")
        """
        Cool! Time to actually set the exposure.
        """
        result = dll.set_property(self.handle, 4, exposure_microseconds)
        assert result == dll.success
        self.get_exposure(verbose=verbose)
        return None

    def get_exposure(self, verbose=True):
        exposure = C.c_long(777)
        assert dll.get_property(self.handle, 4, exposure) == dll.success
        self.exposure_microseconds = exposure.value
        if verbose:
            print "Camera exposure (s):", self.exposure_microseconds * 1e-6
        return self.exposure_microseconds

    def start_live(self, verbose=True):
        if verbose: print "Starting live...",
        assert dll.success == dll.start_live(self.handle, 0)
        self.live = True
        if verbose: print "done"
        return None

    def stop_live(self, verbose=True):
        if verbose: print "Stopping live...",
        assert dll.success == dll.stop_live(self.handle)
        self.live = False
        if verbose: print "done"
        return None

    def snap(self, filename=None, verbose=True):
        if verbose: print "Snapping:",
        if self.live:
            already_live = True
        else:
            self.start_live(verbose=verbose)
            already_live = False            
        assert dll.success == dll.snap_image(self.handle, -1)
        if not already_live:
            self.stop_live(verbose=verbose)
        ptr = dll.get_image_pointer(self.handle)
        image_buffer = buffer_from_memory(
            ptr,
            self.width * self.height * self.bit_depth // 8)
        image = np.frombuffer(image_buffer, np.uint16)
        image = image.reshape(1, self.height, self.width)
        image = np.right_shift(image, 4)
        if verbose:
            print image.shape, image.dtype,
            print image.min(), image.max(), image.mean()
        if filename is not None:
            assert filename.endswith('.tif')
            simple_tif.array_to_tif(image, filename)
        return None

    def enable_trigger(self, enable):
        """
        Enable or disable camera triggering.

        enable: True to enable the trigger, False to disable.
        """
        assert dll.is_trigger_available(self.handle) == 1
        result = dll.IC_EnableTrigger(self.handle, int(enable))
##        if result != 1:
##            raise UserWarning("Enable trigger failed")


"""
Structure definitions
"""
class GrabberHandle_t(C.Structure):
    _fields_ = [('unused', C.c_int)]

GrabberHandle = C.POINTER(GrabberHandle_t)

"""
DLL management
"""
try:
    dll = C.windll.LoadLibrary('tisgrabber_x64')
    assert dll.IC_InitLibrary(0) == 1
except (WindowsError, AssertionError):
    print "Failed to load or initialize tisgrabber_x64.dll"
    print "You need this to run cameras from TheImagingSource"
    print "You also need TIS_DShowLib10_x64.dll and TIS_UDSHL10_x64.dll"
    print "You get these three DLLs from TheImagingSource's website."
    raise

dll.success = 1
dll.error = 0
dll.no_handle = -1
dll.no_device = -2
dll.Y16 = 4
dll.exposure = 4

dll.get_device_count = dll.IC_GetDeviceCount
dll.get_device_count.argtypes = []
dll.get_device_count.restype = C.c_int
                      
dll.get_unique_name_from_list = dll.IC_GetUniqueNamefromList
dll.get_unique_name_from_list.argtypes = [C.c_int]
dll.get_unique_name_from_list.restype = C.c_char_p

##dll.get_unique_name = dll.IC_GetUniqueName
##dll.get_unique_name.argtypes = [GrabberHandle, C.c_char_p, C.c_int]
##dll.get_unique_name.restype = C.c_int

dll.create_grabber = dll.IC_CreateGrabber
dll.create_grabber.argtypes = []
dll.create_grabber.restype = GrabberHandle

dll.open_by_name = dll.IC_OpenDevByUniqueName
dll.open_by_name.argtypes = [GrabberHandle, C.c_char_p]
dll.open_by_name.restype = C.c_int

dll.is_valid = dll.IC_IsDevValid
dll.is_valid.argtypes = [GrabberHandle]
dll.is_valid.restype = C.c_int

dll.reset_to_default = dll.IC_ResetProperties
dll.reset_to_default.argtypes = [GrabberHandle]
dll.reset_to_default.restype = C.c_int

dll.remove_overlay = dll.IC_RemoveOverlay
dll.remove_overlay.argtypes = [GrabberHandle, C.c_int]

dll.get_video_format_count = dll.IC_GetVideoFormatCount
dll.get_video_format_count.argtypes = [GrabberHandle]
dll.get_video_format_count.restype = C.c_int

dll.get_video_format = dll.IC_GetVideoFormat
dll.get_video_format.argtypes = [GrabberHandle, C.c_int]
dll.get_video_format.restype = C.c_char_p

dll.set_video_format = dll.IC_SetVideoFormat
dll.set_video_format.argtypes = [GrabberHandle, C.c_char_p]
dll.set_video_format.restype = C.c_int

dll.get_image_description = dll.IC_GetImageDescription
dll.get_image_description.argtypes = [GrabberHandle,
                                      C.POINTER(C.c_long),
                                      C.POINTER(C.c_long),
                                      C.POINTER(C.c_int),
                                      C.POINTER(C.c_int)]
dll.get_image_description.restype = C.c_int

dll.get_width = dll.IC_GetVideoFormatWidth
dll.get_width.argtypes = [GrabberHandle]
dll.get_width.restype = C.c_int

dll.get_height = dll.IC_GetVideoFormatHeight
dll.get_height.argtypes = [GrabberHandle]
dll.get_height.restype = C.c_int

dll.get_format = dll.IC_GetFormat
dll.get_format.argtypes = [GrabberHandle]
dll.get_format.restype = C.c_int

dll.set_format = dll.IC_SetFormat
dll.set_format.argtypes = [GrabberHandle, C.c_int]
dll.set_format.restype = C.c_int

dll.get_auto_property = dll.IC_GetAutoCameraProperty
dll.get_auto_property.argtypes = [GrabberHandle, C.c_int, C.POINTER(C.c_int)]
dll.get_auto_property.restpye = C.c_int

dll.set_auto_property = dll.IC_EnableAutoCameraProperty
dll.set_auto_property.argtypes = [GrabberHandle, C.c_int, C.c_int]
dll.set_auto_property.restpye = C.c_int

dll.get_property = dll.IC_GetCameraProperty
dll.get_property.argtypes = [GrabberHandle, C.c_uint, C.POINTER(C.c_long)]
dll.get_property.restype = C.c_int

dll.get_property_range = dll.IC_CameraPropertyGetRange
dll.get_property_range.argtypes = [GrabberHandle,
                                   C.c_uint,
                                   C.POINTER(C.c_long),
                                   C.POINTER(C.c_long)]
dll.get_property.restype = C.c_int

dll.set_property = dll.IC_SetCameraProperty
dll.set_property.argtypes = [GrabberHandle, C.c_uint, C.c_long]
dll.set_property.restype = C.c_int

dll.start_live = dll.IC_StartLive
dll.start_live.argtypes = [GrabberHandle, C.c_int]
dll.start_live.restype = C.c_int

dll.stop_live = dll.IC_StopLive
dll.stop_live.argtypes = [GrabberHandle]

dll.snap_image = dll.IC_SnapImage
dll.snap_image.argtypes = [GrabberHandle, C.c_int]
dll.snap_image.restype = C.c_int

dll.get_image_pointer = dll.IC_GetImagePtr
dll.get_image_pointer.argtypes = [GrabberHandle]
dll.get_image_pointer.restype = C.c_void_p

dll.is_trigger_available = dll.IC_IsTriggerAvailable
dll.is_trigger_available.argtypes = [GrabberHandle]
dll.is_trigger_available.restype = C.c_int

dll.enable_trigger = dll.IC_EnableTrigger
dll.enable_trigger.argtypes = [GrabberHandle, C.c_int]
dll.enable_trigger.restype = C.c_int

buffer_from_memory = C.pythonapi.PyBuffer_FromMemory
buffer_from_memory.restype = C.py_object

"""
Test code
"""
if __name__ == '__main__':
    camera = DMK_23GP031()
    camera.set_video_format("Y16 (1280x1024)")
##    camera.enable_trigger(True)
    camera.start_live()
    start = time.clock()
    num_frames = 10
    for i in range(num_frames):
        camera.snap(verbose=False)
##        camera.snap(('image_{}.tif'.format(i)), verbose=False)
    end = time.clock()
    camera.stop_live()
    print num_frames * 1.0 / (end - start), "frames per second"
