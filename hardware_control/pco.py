import os, ctypes, time
try:
    import numpy
except ImportError:
    print "In pco.py, numpy could not be imported."
    print "You won't be able to use record_to_memory()."

PCO_api = ctypes.oledll.LoadLibrary("SC2_Cam")
"""Requires sc2_cl_me4.dll to be in the same directory.
If you get a WindowsError, read PCO_err.h to decypher it."""

libc = ctypes.cdll.msvcrt
libc.fopen.restype = ctypes.c_void_p

class Edge:
    def __init__(self):
        self.camera_handle = ctypes.c_void_p()
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
        self.armed = False
        return None

    def apply_settings(
        self, trigger='auto trigger', exposure_time_microseconds=2200,
        region_of_interest=(961, 841, 1440, 1320), verbose=True):
        
        self.disarm(verbose=verbose)
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
        response = PCO_api.PCO_GetCameraHealthStatus(
            self.camera_handle,
            ctypes.byref(dwWarn), ctypes.byref(dwErr), ctypes.byref(dwStatus))
        if verbose:
            print " Camera health status (0 0 0 means healthy):",
            print dwWarn.value, dwErr.value, dwStatus.value
        if dwWarn.value != 0 or dwErr.value != 0 or dwStatus.value != 0:
            raise UserWarning("Camera unhealthy: %x %x %x %i"%(
                dwWarn.value, dwErr.value, dwStatus.value, response))

        if verbose:
            print "Reading temperatures..."
        ccdtemp, camtemp, powtemp = (
            ctypes.c_int16(), ctypes.c_int16(), ctypes.c_int16())
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
        trigger_mode_names = {0: "auto trigger",
                      1: "software trigger",
                      2: "external trigger/software exposure control",
                      3: "external exposure control"}
        mode_name_to_number = dict(
            (v,k) for k, v in trigger_mode_names.iteritems())
        if verbose:
            print "Setting trigger mode..."
        wTriggerMode = ctypes.c_uint16(mode_name_to_number[trigger])
        PCO_api.PCO_SetTriggerMode(self.camera_handle, wTriggerMode)
        PCO_api.PCO_GetTriggerMode(
            self.camera_handle, ctypes.byref(wTriggerMode))
        if verbose:
            print " Trigger mode is", trigger_mode_names[wTriggerMode.value]

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

        x0, y0, x1, y1 = enforce_roi(region_of_interest, verbose=verbose)

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

        trigger = trigger_mode_names[wTriggerMode.value]
        """Exposure is in microseconds"""
        exposure = dwExposure.value * 10.**(3*wTimeBaseExposure.value - 3)
        roi = (wRoiX0.value, wRoiY0.value,
               wRoiX1.value, wRoiY1.value)
        return (trigger, exposure, roi)

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
            ctypes.c_int16(), ctypes.c_int16(), ctypes.c_int16())
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
        trigger_mode_names = {0: "auto trigger",
                              1: "software trigger",
                              2: "external trigger/software exposure control",
                              3: "external exposure control"}
        mode_name_to_number = dict((v,k) for k, v in mode_names.iteritems())
        wTriggerMode = ctypes.c_uint16()
        PCO_api.PCO_GetTriggerMode(
            self.camera_handle, ctypes.byref(wTriggerMode))
        if verbose:
            print " Trigger mode is", trigger_mode_names[wTriggerMode.value]

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

        trigger = trigger_mode_names[wTriggerMode.value]
        """Exposure is in microseconds"""
        exposure = dwExposure.value * 10.**(3*wTimeBaseExposure.value - 3)
        roi = (wRoiX0.value, wRoiY0.value,
               wRoiX1.value, wRoiY1.value)
        return (trigger, exposure, roi)
    
    def arm(self, num_buffers=2, verbose=False):
        if self.armed:
            raise UserWarning('The pco.edge camera is already armed.')
        if verbose:
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
            self.buffer_events.append(ctypes.c_void_p(0))
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
        message = PCO_api.PCO_SetRecordingState(self.camera_handle, wRecState)
        if verbose:
            print "Recording state return value:", message
        self.armed = True
        return None

    def disarm(self, verbose=True):
        wRecState = ctypes.c_uint16(0) #Turn off recording
        PCO_api.PCO_SetRecordingState(self.camera_handle, wRecState)
        PCO_api.PCO_RemoveBuffer(self.camera_handle)
        for buf in self.buffer_numbers: #Free any allocated buffers
            PCO_api.PCO_FreeBuffer(self.camera_handle, buf)
        self.buffer_numbers, self.buffer_pointers, self.buffer_events = (
            [], [], [])
        self.armed = False
        return None

    def record_to_file(
        self, num_images, preframes=0,
        file_name='image.raw', save_path=None, verbose=False,
        poll_timeout=5e5):
        """Call this any number of times, after arming the camera once"""

        if save_path is None:
            save_path = os.getcwd()
        save_path = str(save_path)

        dw1stImage, dwLastImage = ctypes.c_uint32(0), ctypes.c_uint32(0)
        wBitsPerPixel = ctypes.c_uint16(16) #16 bits for the pco.edge, right?
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
                if num_polls > poll_timeout:
                    libc.fclose(file_pointer)
                    raise UserWarning("After %i polls, no buffer."%poll_timeout)

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
        wBitsPerPixel = ctypes.c_uint16(16) #16 bits for the pco.edge, right?
        dwStatusDll, dwStatusDrv = ctypes.c_uint32(), ctypes.c_uint32()
        bytes_per_pixel = ctypes.c_uint32(2)
        pixels_per_image = ctypes.c_uint32(self.wXRes.value * self.wYRes.value)
        added_buffers = []
        for which_buf in range(len(self.buffer_numbers)):
            PCO_api.PCO_AddBufferEx(
                self.camera_handle, dw1stImage, dwLastImage,
                self.buffer_numbers[which_buf], self.wXRes, self.wYRes,
                wBitsPerPixel)
            added_buffers.append(which_buf)
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
            added_buffers,
            buffer_from_memory)
        return None

    def record_to_memory(
        self, num_images, preframes=0, verbose=False, out=None,
        poll_timeout=5e5):
        """Call this any number of times, after arming the camera once"""

        if not hasattr(self, '_prepared_to_record'):
            self._prepare_to_record_to_memory()
        (dw1stImage, dwLastImage,
         wBitsPerPixel,
         dwStatusDll, dwStatusDrv,
         bytes_per_pixel, pixels_per_image,
         added_buffers,
         buffer_from_memory
         ) = self._prepared_to_record

        if out is None:
            assert bytes_per_pixel.value == 2
            out = numpy.ones(
                (num_images, self.wYRes.value, self.wXRes.value),
                dtype=numpy.uint16)
        else:
            try:
                assert out.shape == (
                    num_images, self.wYRes.value, self.wXRes.value)
            except AssertionError:
                print out.shape
                print (num_images, self.wYRes.value, self.wXRes.value)
                raise UserWarning(
                    "Input argument 'out' must have dimensions:\n" +
                    "(num_images, y-resolution, x-resolution)")
            except AttributeError:
                raise UserWarning("Input argument 'out' must be a numpy array.")

        num_acquired = 0
        for which_im in range(num_images):
            num_polls = 0
            polling = True
            while polling:
                num_polls += 1
                message = PCO_api.PCO_GetBufferStatus(
                    self.camera_handle, self.buffer_numbers[added_buffers[0]],
                    ctypes.byref(dwStatusDll), ctypes.byref(dwStatusDrv))
                if dwStatusDll.value == 0xc0008000:
                    which_buf = added_buffers.pop(0) #Buffer exits the queue                        
                    if verbose:
                        print "After", num_polls, "polls, buffer",
                        print self.buffer_numbers[which_buf].value,
                        print "is ready."
                    polling = False
                    break
                else:
                    time.sleep(0.00005) #Wait 50 microseconds
                if num_polls > poll_timeout:
                    raise TimeoutError(
                        "After %i polls, no buffer."%(poll_timeout),
                        num_acquired=num_acquired)
            if dwStatusDrv.value == 0x0L:
                pass
            elif dwStatusDrv.value == 0x80332028:
                raise DMAError('DMA error during record_to_memory')
            else:
                print "dwStatusDrv:", dwStatusDrv.value
                raise UserWarning("Buffer status error")

            if verbose:
                print "Record to memory result:",
                print hex(dwStatusDll.value), hex(dwStatusDrv.value), message

            if which_im >= preframes:
                buf = buffer_from_memory(self.buffer_pointers[which_buf],
                                         2*(out.shape[1]*out.shape[2]))
                out[which_im - preframes, :, :] = numpy.frombuffer(
                    buf, numpy.uint16).reshape(out.shape[1:])
                num_acquired += 1

            PCO_api.PCO_AddBufferEx(#Put the buffer back in the queue
                self.camera_handle, dw1stImage, dwLastImage,
                self.buffer_numbers[which_buf], self.wXRes, self.wYRes,
                wBitsPerPixel)
            added_buffers.append(which_buf)
        return out

    def _set_hw_io_ch4_to_global_exposure(self, verbose=True):
        class HWIOSignalTimingStructureIn(ctypes.Structure):
                        _fields_ = [("code", ctypes.c_uint16),
                                    ("length", ctypes.c_uint16),
                                    ("index", ctypes.c_uint16),
                                    ("select", ctypes.c_uint16),
                                    ("parameter", ctypes.c_uint32),
                                    ("Reserved0", ctypes.c_uint32),
                                    ("Reserved1", ctypes.c_uint32),
                                    ("Reserved2", ctypes.c_uint32),
                                    ("Reserved3", ctypes.c_uint32),
                                    ("checksum", ctypes.c_uint8)]

        class HWIOSignalTimingStructureOut(ctypes.Structure):
                        _fields_ = [("code", ctypes.c_uint16),
                                    ("length", ctypes.c_uint16),
                                    ("index", ctypes.c_uint16),
                                    ("select", ctypes.c_uint16),
                                    ("type", ctypes.c_uint32),
                                    ("parameter", ctypes.c_uint32),
                                    ("Reserved0", ctypes.c_uint32),
                                    ("Reserved1", ctypes.c_uint32),
                                    ("Reserved2", ctypes.c_uint32),
                                    ("Reserved3", ctypes.c_uint32),
                                    ("checksum", ctypes.c_uint8)]
        message = HWIOSignalTimingStructureIn()
        response = HWIOSignalTimingStructureOut()

        message.code = 0x2712;          ## Set HWIO Signal Timing command
        message.length = 0x001D;        ## Add up all the bytes, 29 in total
        message.index = 0x0003;         ## Fourth signal (0 - 3) is exposure out
        message.select = 0x0000;        ## Function as Exposure Output
        message.parameter = 0x00000002; ## 1 for rolling ; 2 for global
        response.length = 0x0021;

        if verbose:
            print "Setting hardware I/O signal..."
        PCO_api.PCO_ControlCommandCall(self.camera_handle,
                                       ctypes.byref(message), message.length,
                                       ctypes.byref(response), response.length)
        if verbose:
            print "Index:", response.index
            print "Type:", response.type, "(if 7, rolling shutter exposure)"
            print "Parameter:", response.parameter
        return None

    def close(self, verbose=True):
        print "Ending recording..."
        self.disarm(verbose=verbose)
        PCO_api.PCO_CloseCamera(self.camera_handle)
        print "Camera closed."
        return None

class TimeoutError(Exception):
    def __init__(self, value, num_acquired=0):
        self.value = value
        self.num_acquired = num_acquired
    def __str__(self):
        return repr(self.value)

class DMAError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def enforce_roi(region_of_interest, verbose):
    x0, y0, x1, y1 = tuple(region_of_interest)
    if verbose:
        print "ROI requested:", x0, y0, x1, y1
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
    if verbose:
        print "Nearest possible ROI:", x0, y0, x1, y1
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
    camera.apply_settings(region_of_interest=(641, 841, 1440, 1320))
    camera.get_settings(verbose=False)
    camera.arm(num_buffers=3)
    camera._prepare_to_record_to_memory()
##    for i in range(100):
##        times.append(time.clock())
##        camera.record_to_file(num_images=1, file_name='%06i.raw'%(i))
##    camera.close()
    print "Acquiring..."
    for i in range(100):
        times.append(time.clock())
        images = camera.record_to_memory(num_images=1, verbose=False)
    times.append(time.clock())
    camera.close()

    try:
        import matplotlib
        matplotlib.use('TkAgg')
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
        from matplotlib.figure import Figure
        import Tkinter as Tk
        root = Tk.Tk()
        root.wm_title("Performance")
        f = Figure(figsize=(5,4), dpi=100)
        a = f.add_subplot(111)
        a.plot(1000*numpy.diff(times), '.-')
        a.set_ylabel('milliseconds')
        a.set_xlabel('Frame #')
        a.grid()
        canvas = FigureCanvasTkAgg(f, master=root)
        canvas.show()
        canvas.get_tk_widget().pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
        toolbar = NavigationToolbar2TkAgg( canvas, root )
        toolbar.update()
        canvas._tkcanvas.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
        def _quit():
            root.quit()     # stops mainloop
            root.destroy()  # this is necessary on Windows to prevent
                            # Fatal Python Error: PyEval_RestoreThread: NULL tstate
        button = Tk.Button(master=root, text='Quit', command=_quit)
        button.pack(side=Tk.BOTTOM)
        Tk.mainloop()
        # If you put root.destroy() here, it will cause an error if
        # the window is closed with the window manager.
    except:
        pass ##
