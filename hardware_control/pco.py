import os, ctypes, time
try:
    import numpy
except ImportError:
    print "Numpy could not be imported."
    print "You won't be able to use record_to_memory()."

PCO_api = ctypes.oledll.LoadLibrary("SC2_Cam")
"""Requires sc2_cl_me4.dll to be in the same directory.
If you get a WindowsError, read PCO_err.h to decypher it."""

libc = ctypes.cdll.msvcrt
libc.fopen.restype = ctypes.c_void_p

class Edge:
    def __init__(self):
        self.camera_handle = ctypes.c_uint64() ##Assuming a 64-bit platform
        print "Opening camera..."
        try:
            PCO_api.PCO_OpenCamera(ctypes.byref(self.camera_handle), 0)
        except WindowsError:
            print "\n\n Failed to open the camera. Is Camware open?\n\n"
            raise
        wRecState = ctypes.c_uint16(0) #Turn off recording
        PCO_api.PCO_SetRecordingState(self.camera_handle, wRecState)
        print " Camera handle:", self.camera_handle.value
        self.buffer_numbers = []
        return None

    def apply_settings(
        self, trigger='auto trigger', exposure_time_microseconds=2200,
        region_of_interest=(961, 841, 1440, 1320), verbose=True):
        wRecState = ctypes.c_uint16(0) #Turn off recording
        PCO_api.PCO_SetRecordingState(self.camera_handle, wRecState)
        for buf in self.buffer_numbers: #Free any allocated buffers
            PCO_api.PCO_FreeBuffer(self.camera_handle, buf)

        PCO_api.PCO_ResetSettingsToDefault(self.camera_handle)

        wSensor = ctypes.c_uint16(0)
        if verbose:
            print "Setting sensor format..."
        PCO_api.PCO_SetSensorFormat(self.camera_handle, wSensor)
        PCO_api.PCO_GetSensorFormat(self.camera_handle, ctypes.byref(wSensor))
        mode_names = {0: "standard", 1:"extended"}
        if verbose:
            print " Sensor format is", mode_names[wSensor.value]

        if verbose:
            print "Getting camera health status..."
        dwWarn, dwErr, dwStatus = (
            ctypes.c_uint32(), ctypes.c_uint32(), ctypes.c_uint32())
        PCO_api.PCO_GetCameraHealthStatus(
            self.camera_handle,
            ctypes.byref(dwWarn), ctypes.byref(dwErr), ctypes.byref(dwStatus))
        if verbose:
            print " Camera health status (0 0 0 means healthy):",
            print dwWarn.value, dwErr.value, dwStatus.value

        if verbose:
            print "Reading temperatures..."
        ccdtemp, camtemp, powtemp = (
            ctypes.c_short(), ctypes.c_short(), ctypes.c_short())
        PCO_api.PCO_GetTemperature(
            self.camera_handle,
            ctypes.byref(ccdtemp), ctypes.byref(camtemp), ctypes.byref(powtemp))
        if verbose:
            print " CCD temperature:", ccdtemp.value * 0.1, "C"
            print " Camera temperature:", camtemp.value, "C"
            print " Power supply temperature:", powtemp.value, "C"

        """
        0x0000 = [auto trigger]
        A new image exposure is automatically started best possible
        compared to the readout of an image. If a CCD is used and the
        images are taken in a sequence, then exposures and sensor readout
        are started simultaneously. Signals at the trigger input (<exp
        trig>) are irrelevant.
        - 0x0001 = [software trigger]:
        An exposure can only be started by a force trigger command.
        - 0x0002 = [extern exposure & software trigger]:
        A delay / exposure sequence is started at the RISING or FALLING
        edge (depending on the DIP switch setting) of the trigger input
        (<exp trig>).
        - 0x0003 = [extern exposure control]:
        The exposure time is defined by the pulse length at the trigger
        input(<exp trig>). The delay and exposure time values defined by
        the set/request delay and exposure command are ineffective.
        (Exposure time length control is also possible for double image
        mode; exposure time of the second image is given by the readout
        time of the first image.)
        """
        mode_names = {0: "auto trigger",
                      1: "software trigger",
                      2: "external trigger/software exposure control",
                      3: "external exposure control"}
        mode_name_to_number = dict((v,k) for k, v in mode_names.iteritems())
        if verbose:
            print "Setting trigger mode..."
        wTriggerMode = ctypes.c_uint16(mode_name_to_number[trigger])
        PCO_api.PCO_SetTriggerMode(self.camera_handle, wTriggerMode)
        PCO_api.PCO_GetTriggerMode(
            self.camera_handle, ctypes.byref(wTriggerMode))
        if verbose:
            print " Trigger mode is", mode_names[wTriggerMode.value]

        wStorageMode = ctypes.c_uint16()
        PCO_api.PCO_GetStorageMode(
            self.camera_handle, ctypes.byref(wStorageMode))
        mode_names = {0: "Recorder", 1: "FIFO buffer"} #Not critical for pco.edge
        if verbose:
            print "Storage mode:", mode_names[wStorageMode.value]

        if verbose:
            print "Setting recorder submode..."
        wRecSubmode = ctypes.c_uint16(1)
        PCO_api.PCO_SetRecorderSubmode(self.camera_handle, wRecSubmode)
        PCO_api.PCO_GetRecorderSubmode(
            self.camera_handle, ctypes.byref(wRecSubmode))
        mode_names = {0: "sequence", 1: "ring buffer"}
        if verbose:
            print " Recorder submode:", mode_names[wRecSubmode.value]

        if verbose:
            print "Setting acquire mode..."
        wAcquMode = ctypes.c_uint16(0)
        PCO_api.PCO_SetAcquireMode(self.camera_handle, wAcquMode)
        PCO_api.PCO_GetAcquireMode(self.camera_handle, ctypes.byref(wAcquMode))
        mode_names = {0: "auto", 1:"external (static)", 2:"external (dynamic)"}
        if verbose:
            print " Acquire mode:", mode_names[wAcquMode.value]

        if verbose:
            print "Setting pixel rate..."
        dwPixelRate = ctypes.c_uint32(286000000)
        PCO_api.PCO_SetPixelRate(self.camera_handle, dwPixelRate)
        PCO_api.PCO_GetPixelRate(self.camera_handle, ctypes.byref(dwPixelRate))
        if verbose:
            print " Pixel rate:", dwPixelRate.value

        if verbose:
            print "Setting delay and exposure time..."
        dwDelay = ctypes.c_uint32(0)
        wTimeBaseDelay = ctypes.c_uint16(0)
        dwExposure = ctypes.c_uint32(int(exposure_time_microseconds))
        wTimeBaseExposure = ctypes.c_uint16(1)
        PCO_api.PCO_SetDelayExposureTime(
            self.camera_handle,
            dwDelay, dwExposure, wTimeBaseDelay, wTimeBaseExposure)
        PCO_api.PCO_GetDelayExposureTime(
            self.camera_handle,
            ctypes.byref(dwDelay), ctypes.byref(dwExposure),
            ctypes.byref(wTimeBaseDelay), ctypes.byref(wTimeBaseExposure))
        mode_names = {0: "nanoseconds", 1: "microseconds", 2: "milliseconds"}
        if verbose:
            print " Exposure:", dwExposure.value, mode_names[wTimeBaseExposure.value]
            print " Delay:", dwDelay.value, mode_names[wTimeBaseDelay.value]

        x0, y0, x1, y1 = enforce_roi(region_of_interest)

        wRoiX0, wRoiY0, wRoiX1, wRoiY1 = (
            ctypes.c_uint16(x0), ctypes.c_uint16(y0),
            ctypes.c_uint16(x1), ctypes.c_uint16(y1))
        if verbose:
            print "Setting sensor ROI..."
        PCO_api.PCO_SetROI(self.camera_handle, wRoiX0, wRoiY0, wRoiX1, wRoiY1)
        PCO_api.PCO_GetROI(self.camera_handle,
                           ctypes.byref(wRoiX0), ctypes.byref(wRoiY0),
                           ctypes.byref(wRoiX1), ctypes.byref(wRoiY1))
        if verbose:
            print " Camera ROI:"
            """We typically use 841 to 1320 u/d, 961 to 1440 l/r"""
            print "  From pixel", wRoiX0.value, "to pixel", wRoiX1.value, "(left/right)"
            print "  From pixel", wRoiY0.value, "to pixel", wRoiY1.value, "(up/down)"
            print

        if hasattr(self, '_prepared_to_record'):
            del self._prepared_to_record
        return None

    def get_settings(self, verbose=True):
        if verbose:
            print "Retrieving settings from camera..."
        wSensor = ctypes.c_uint16(0)
        PCO_api.PCO_GetSensorFormat(self.camera_handle, ctypes.byref(wSensor))
        mode_names = {0: "standard", 1:"extended"}
        if verbose:
            print " Sensor format is", mode_names[wSensor.value]

        dwWarn, dwErr, dwStatus = (
            ctypes.c_uint32(), ctypes.c_uint32(), ctypes.c_uint32())
        PCO_api.PCO_GetCameraHealthStatus(
            self.camera_handle,
            ctypes.byref(dwWarn), ctypes.byref(dwErr), ctypes.byref(dwStatus))
        if verbose:
            print " Camera health status (0 0 0 means healthy):",
            print dwWarn.value, dwErr.value, dwStatus.value

        ccdtemp, camtemp, powtemp = (
            ctypes.c_short(), ctypes.c_short(), ctypes.c_short())
        PCO_api.PCO_GetTemperature(
            self.camera_handle,
            ctypes.byref(ccdtemp), ctypes.byref(camtemp), ctypes.byref(powtemp))
        if verbose:
            print " CCD temperature:", ccdtemp.value * 0.1, "C"
            print " Camera temperature:", camtemp.value, "C"
            print " Power supply temperature:", powtemp.value, "C"

        """
        0x0000 = [auto trigger]
        A new image exposure is automatically started best possible
        compared to the readout of an image. If a CCD is used and the
        images are taken in a sequence, then exposures and sensor readout
        are started simultaneously. Signals at the trigger input (<exp
        trig>) are irrelevant.
        - 0x0001 = [software trigger]:
        An exposure can only be started by a force trigger command.
        - 0x0002 = [extern exposure & software trigger]:
        A delay / exposure sequence is started at the RISING or FALLING
        edge (depending on the DIP switch setting) of the trigger input
        (<exp trig>).
        - 0x0003 = [extern exposure control]:
        The exposure time is defined by the pulse length at the trigger
        input(<exp trig>). The delay and exposure time values defined by
        the set/request delay and exposure command are ineffective.
        (Exposure time length control is also possible for double image
        mode; exposure time of the second image is given by the readout
        time of the first image.)
        """
        mode_names = {0: "auto trigger",
                      1: "software trigger",
                      2: "external trigger/software exposure control",
                      3: "external exposure control"}
        mode_name_to_number = dict((v,k) for k, v in mode_names.iteritems())
        wTriggerMode = ctypes.c_uint16()
        PCO_api.PCO_GetTriggerMode(
            self.camera_handle, ctypes.byref(wTriggerMode))
        if verbose:
            print " Trigger mode is", mode_names[wTriggerMode.value]

        wStorageMode = ctypes.c_uint16()
        PCO_api.PCO_GetStorageMode(
            self.camera_handle, ctypes.byref(wStorageMode))
        mode_names = {0: "Recorder", 1: "FIFO buffer"} #Not critical for pco.edge
        if verbose:
            print "Storage mode:", mode_names[wStorageMode.value]

        wRecSubmode = ctypes.c_uint16(1)
        PCO_api.PCO_GetRecorderSubmode(
            self.camera_handle, ctypes.byref(wRecSubmode))
        mode_names = {0: "sequence", 1: "ring buffer"}
        if verbose:
            print " Recorder submode:", mode_names[wRecSubmode.value]

        wAcquMode = ctypes.c_uint16(0)
        PCO_api.PCO_GetAcquireMode(self.camera_handle, ctypes.byref(wAcquMode))
        mode_names = {0: "auto", 1:"external (static)", 2:"external (dynamic)"}
        if verbose:
            print " Acquire mode:", mode_names[wAcquMode.value]

        dwPixelRate = ctypes.c_uint32(286000000)
        PCO_api.PCO_GetPixelRate(self.camera_handle, ctypes.byref(dwPixelRate))
        if verbose:
            print " Pixel rate:", dwPixelRate.value

        dwDelay = ctypes.c_uint32(0)
        wTimeBaseDelay = ctypes.c_uint16(0)
        dwExposure = ctypes.c_uint32(0)
        wTimeBaseExposure = ctypes.c_uint16(1)
        PCO_api.PCO_GetDelayExposureTime(
            self.camera_handle,
            ctypes.byref(dwDelay), ctypes.byref(dwExposure),
            ctypes.byref(wTimeBaseDelay), ctypes.byref(wTimeBaseExposure))
        mode_names = {0: "nanoseconds", 1: "microseconds", 2: "milliseconds"}
        if verbose:
            print " Exposure:", dwExposure.value, mode_names[wTimeBaseExposure.value]
            print " Delay:", dwDelay.value, mode_names[wTimeBaseDelay.value]

        wRoiX0, wRoiY0, wRoiX1, wRoiY1 = (
            ctypes.c_uint16(), ctypes.c_uint16(),
            ctypes.c_uint16(), ctypes.c_uint16())
        PCO_api.PCO_GetROI(self.camera_handle,
                           ctypes.byref(wRoiX0), ctypes.byref(wRoiY0),
                           ctypes.byref(wRoiX1), ctypes.byref(wRoiY1))
        if verbose:
            print " Camera ROI:"
            """We typically use 841 to 1320 u/d, 961 to 1440 l/r"""
            print "  From pixel", wRoiX0.value, "to pixel", wRoiX1.value, "(left/right)"
            print "  From pixel", wRoiY0.value, "to pixel", wRoiY1.value, "(up/down)"
            print

        trigger = mode_names[wTriggerMode.value]
        exposure = (dwExposure.value, mode_names[wTimeBaseExposure.value])
        roi = (wRoiX0.value, wRoiX1.value,
               wRoiY0.value, wRoiY1.value)
        return (trigger, exposure, roi)
    
    def arm(self, num_buffers=2, verbose=False):
        print "Arming camera..." 
        PCO_api.PCO_ArmCamera(self.camera_handle)
        self.wXRes, self.wYRes, wXResMax, wYResMax = (
            ctypes.c_uint16(), ctypes.c_uint16(),
            ctypes.c_uint16(), ctypes.c_uint16())
        PCO_api.PCO_GetSizes(self.camera_handle,
                             ctypes.byref(self.wXRes), ctypes.byref(self.wYRes),
                             ctypes.byref(wXResMax), ctypes.byref(wYResMax))
        if verbose:
            print "Camera ROI dimensions:",
            print self.wXRes.value, "(l/r) by", self.wYRes.value, "(u/d)"

        dwSize = ctypes.c_uint32(self.wXRes.value * self.wYRes.value * 2)
        self.buffer_numbers, self.buffer_pointers, self.buffer_events = (
            [], [], [])
        for i in range(num_buffers):
            self.buffer_numbers.append(ctypes.c_int16(-1))
            self.buffer_pointers.append(ctypes.c_void_p(0))
            self.buffer_events.append(ctypes.c_ulong(0))
            PCO_api.PCO_AllocateBuffer(
                self.camera_handle, ctypes.byref(self.buffer_numbers[i]),
                dwSize, ctypes.byref(self.buffer_pointers[i]),
                ctypes.byref(self.buffer_events[i]))
            if verbose:
                print "Buffer number", self.buffer_nubmers[i].value,
                print "is at address", self.buffer_pointers[i],
                print "linked to an event containing:",
                print self.buffer_events[i].value

        PCO_api.PCO_CamLinkSetImageParameters(
            self.camera_handle, self.wXRes, self.wYRes)

        wRecState = ctypes.c_uint16(1)
        PCO_api.PCO_SetRecordingState(self.camera_handle, wRecState)
        return None

    def record_to_file(
        self, num_images, preframes=0,
        file_name='image.raw', save_path=None, verbose=False):
        """Call this any number of times, after arming the camera once"""

        if save_path is None:
            save_path = os.getcwd()
        save_path = str(save_path)

        dw1stImage, dwLastImage = ctypes.c_uint32(0), ctypes.c_uint32(0)
        wBitsPerPixel = ctypes.c_uint16(14) #14 bits for the pco.edge, right?
        dwStatusDll, dwStatusDrv = ctypes.c_uint32(), ctypes.c_uint32()
        print "Saving:", repr(os.path.join(save_path, file_name))
        file_pointer = ctypes.c_void_p(
            libc.fopen(os.path.join(save_path, file_name), "wb"))
        bytes_per_pixel = ctypes.c_uint32(2)
        pixels_per_image = ctypes.c_uint32(self.wXRes.value * self.wYRes.value)
        for which_im in range(num_images):
            which_buf = which_im % len(self.buffer_numbers)
            PCO_api.PCO_AddBufferEx(
                self.camera_handle, dw1stImage, dwLastImage,
                self.buffer_numbers[which_buf], self.wXRes, self.wYRes,
                wBitsPerPixel)
            
            num_polls = 0
            while True:
                num_polls += 1
                PCO_api.PCO_GetBufferStatus(
                    self.camera_handle, self.buffer_numbers[which_buf],
                    ctypes.byref(dwStatusDll), ctypes.byref(dwStatusDrv))
                time.sleep(0.00005) #50 microseconds
                if dwStatusDll.value == 0xc0008000:
                    if verbose:
                        print "After", num_polls, "polls, buffer",
                        print self.buffer_numbers[which_buf].value, "is ready."
                    break
                if num_polls > 5e5:
                    libc.fclose(file_pointer)
                    raise UserWarning("After half a  million polls, no buffer.")

            if which_im >= preframes:
                response = libc.fwrite(
                    self.buffer_pointers[which_buf],
                    bytes_per_pixel, pixels_per_image, file_pointer)
                if response != pixels_per_image.value:
                    raise UserWarning("Not enough data written to image file.")
                    libc.fclose(file_pointer)

        libc.fclose(file_pointer)
        print "Saving:", repr(os.path.splitext(os.path.join(
            save_path, file_name))[0] + '.txt')
        file_info = open(os.path.splitext(os.path.join(
            save_path, file_name))[0] + '.txt', 'wb')
        file_info.write('Left/right: %i pixels\r\n'%(self.wXRes.value))
        file_info.write('Up/down: %i pixels\r\n'%(self.wYRes.value))
        file_info.write('Number of images: %i\r\n'%(num_images - preframes))
        file_info.write('Data type: 16-bit unsigned integers\r\n')
        file_info.write('Byte order: Intel (little-endian)')
        file_info.close()

        print num_images, "images recorded."
        return None

    def _prepare_to_record_to_memory(self):
        dw1stImage, dwLastImage = ctypes.c_uint32(0), ctypes.c_uint32(0)
        wBitsPerPixel = ctypes.c_uint16(14) #14 bits for the pco.edge, right?
        dwStatusDll, dwStatusDrv = ctypes.c_uint32(), ctypes.c_uint32()
        bytes_per_pixel = ctypes.c_uint32(2)
        pixels_per_image = ctypes.c_uint32(self.wXRes.value * self.wYRes.value)
        """
        Gibberish below courtesy of:
        http://stackoverflow.com/questions/4355524/getting-data-from-ctypes-array-into-numpy
        """
        buffer_from_memory = ctypes.pythonapi.PyBuffer_FromMemory
        buffer_from_memory.restype = ctypes.py_object
        self._prepared_to_record = (
            dw1stImage, dwLastImage,
            wBitsPerPixel,
            dwStatusDll, dwStatusDrv,
            bytes_per_pixel, pixels_per_image,
            buffer_from_memory)
        return None

    def record_to_memory(
        self, num_images, preframes=0, verbose=False, out=None):
        """Call this any number of times, after arming the camera once"""

        if not hasattr(self, '_prepared_to_record'):
            self._prepare_to_record_to_memory()
        (dw1stImage, dwLastImage,
         wBitsPerPixel,
         dwStatusDll, dwStatusDrv,
         bytes_per_pixel, pixels_per_image,
         buffer_from_memory
         ) = self._prepared_to_record

        if out is None:
            assert bytes_per_pixel.value == 2
            out = numpy.zeros(
                (num_images, self.wYRes.value, self.wXRes.value),
                dtype=numpy.uint16)
        else:
            try:
                assert out.shape == (
                    num_images, self.wYRes.value, self.wXRes.value)
            except AssertionError:
                print out.shape
                print (num_images, self.wYRes, self.wXRes)
                raise UserWarning(
                    "Input argument 'out' must have dimensions:\n" +
                    "(num_images, y-resolution, x-resolution)")
            except AttributeError:
                raise UserWarning("Input argument 'out' must be a numpy array.")

        for which_im in range(num_images):
            which_buf = which_im % len(self.buffer_numbers)
            PCO_api.PCO_AddBufferEx(
                self.camera_handle, dw1stImage, dwLastImage,
                self.buffer_numbers[which_buf], self.wXRes, self.wYRes,
                wBitsPerPixel)
            
            num_polls = 0
            while True:
                num_polls += 1
                PCO_api.PCO_GetBufferStatus(
                    self.camera_handle, self.buffer_numbers[which_buf],
                    ctypes.byref(dwStatusDll), ctypes.byref(dwStatusDrv))
                time.sleep(0.00005) #50 microseconds
                if dwStatusDll.value == 0xc0008000:
                    if verbose:
                        print "After", num_polls, "polls, buffer",
                        print self.buffer_numbers[which_buf].value, "is ready."
                    break
                if num_polls > 5e5:
                    raise UserWarning("After half a  million polls, no buffer.")

            if which_im >= preframes:
                buf = buffer_from_memory(self.buffer_pointers[which_buf],
                                         2*(out.shape[1]*out.shape[2]))
                out[which_im - preframes, :, :] = numpy.frombuffer(
                    buf, numpy.uint16).reshape(out.shape[1:])
        return out

    def close(self):
        print "Ending recording..."
        wRecState = ctypes.c_uint16(0)
        PCO_api.PCO_SetRecordingState(self.camera_handle, wRecState)
        for buf in self.buffer_numbers:
            PCO_api.PCO_FreeBuffer(self.camera_handle, buf)
        PCO_api.PCO_CloseCamera(self.camera_handle)
        print "Camera closed."
        return None

def enforce_roi(region_of_interest):
    x0, y0, x1, y1 = region_of_interest
    if x0 < 1:
        x0 = 1 #Min value
    if x0 > 2401:
        x0 = 2401 #Max value
    x0 = 1 + 160*((x0 - 1) // 160) #Round to the nearest start
    if x1 < (x0 + 159):
        x1 = x0 + 159
    if x1 > 2560:
        x1 = 2560        
    x1 = x0 -1 + 160 * ((x1 - (x0 - 1))//160) #Round to the nearest end
    if y0 < 1:
        y0 = 1
    if y0 > 1073:
        y0 = 1073
    y1 = 2161 - y0
    return (x0, y0, x1, y1)

"""
##Sample code demonstrating how to save an array with C on Windows.
import numpy, ctypes

libc = ctypes.cdll.msvcrt
libc.fopen.restype = ctypes.c_void_p

data = numpy.arange(10, dtype=numpy.uint16)
data_pointer = numpy.ctypeslib.as_ctypes(data)
bytes_per_pixel = ctypes.c_uint32(numpy.nbytes[data.dtype])
pixels_per_image = ctypes.c_uint32(data.size)

file_pointer = ctypes.c_void_p(
    libc.fopen('test.bin', "wb"))

response = libc.fwrite(
    data_pointer,
    bytes_per_pixel, pixels_per_image, file_pointer)

if response != pixels_per_image.value:
    print "Not enough data written to image file."

libc.fclose(file_pointer)
"""

if __name__ == "__main__":
    import time, numpy
    times = []
    camera = Edge()
    camera.apply_settings(verbose=False)
    camera.get_settings(verbose=False)
    camera.arm()
##    for i in range(3):
##        times.append(time.clock())
##        camera.record_to_file(num_images=120, file_name='%06i.raw'%(i))
##    camera.close()
    for i in range(10):
        times.append(time.clock())
        images = camera.record_to_memory(num_images=1)
    camera.close()
##    import pylab
##    pylab.close('all')
##    fig = pylab.figure()
##    pylab.plot(1000*numpy.diff(times), '.-')
##    pylab.ylabel('milliseconds')
##    pylab.xlabel('Frame #')
##    pylab.title('Camera response time')
##    pylab.grid()
##    fig.show()
##    fig.canvas.draw()
##
##    fig = pylab.figure()
##    pylab.imshow(images[-1, :, :], cmap=pylab.cm.gray, interpolation='nearest')
##    fig.show()
##    fig.canvas.draw()
