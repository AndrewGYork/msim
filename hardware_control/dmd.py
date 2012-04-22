import ctypes
import numpy


DMD_api = ctypes.cdll.LoadLibrary('alpD41')
_ALP_DEFAULT = 0
_ALP_OK = 0
_ALP_DEV_DMDTYPE = 2021
_ALP_DMDTYPE_XGA_055X = 6
_ALP_DATA_FORMAT = 2110

def _check(return_code):
    if return_code != _ALP_OK:
        raise UserWarning("Failed with return code %i"%(return_code))    

def open_dmd():
    """Allocate the ALP high-speed device"""
    print "Allocating DMD device..."
    nDevId = ctypes.c_ulong()
    _check(DMD_api.AlpDevAlloc(
        _ALP_DEFAULT, _ALP_DEFAULT, ctypes.byref(nDevId)))
    print " Device ID:", nDevId.value
    return nDevId

def apply_settings(nDevId, illumination_filename='illumination_pattern.raw',
                   illuminate_time=2200, picture_time=4500, trigger_delay=0):
    """illuminate_time, picture_time, and trigger_delay are in microseconds"""

    print "Applying settings to DMD..."
    """Check the DMD type"""
    nDmdType = ctypes.c_long()
    _check(DMD_api.AlpDevInquire(
        nDevId, _ALP_DEV_DMDTYPE, ctypes.byref(nDmdType)))
    print " DMD type:", nDmdType.value
    if nDmdType.value == _ALP_DMDTYPE_XGA_055X:
        nSizeX, nSizeY = 1024, 768
    else:
        raise UserWarning(
            "What kind of DMD have you got plugged in there, son?")

    """Load the illumination pattern from disk"""
    illumination_pattern = numpy.fromfile(
        illumination_filename, dtype=numpy.uint8)
    num_frames = illumination_pattern.shape[0] // (nSizeX * nSizeY)
    if num_frames * nSizeX * nSizeY == illumination_pattern.shape[0]:
        print " Illumination pattern loaded with", num_frames, "frames."
    else:
        raise UserWarning(
            "Illumination pattern should be a stack of %i by %i images"%(
                nSizeX, nSizeY))
    illumination_pattern_c = numpy.ctypeslib.as_ctypes(illumination_pattern)

    """Allocate a sequence of binary frames"""
    nSeqId = ctypes.c_ulong()
    _check(DMD_api.AlpSeqAlloc( nDevId, 1, num_frames, ctypes.byref(nSeqId) ))
    print " Sequence ID:", nSeqId.value

    """Transmit images into ALP memory"""
    _check(DMD_api.AlpSeqPut(
        nDevId, nSeqId, 0, num_frames, illumination_pattern_c ))
    print " Images transmitted."

    """Set up image timing
    For highest frame rate, first switch to binary uninterrupted mode
    (_ALP_BIN_UNINTERRUPTED) by using AlpDevControl. See also the release
    notes for more details."""
    _check(DMD_api.AlpSeqTiming(
        nDevId, nSeqId,
        int(illuminate_time), int(picture_time), int(trigger_delay),
        _ALP_DEFAULT, _ALP_DEFAULT ))

    paramVal = ctypes.c_long()	
    _check(DMD_api.AlpSeqInquire(
        nDevId, nSeqId, _ALP_DATA_FORMAT, ctypes.byref(paramVal)))
    print " ALP data format:", paramVal.value

    return nSeqId, num_frames

def display_pattern(nDevId, nSeqId):
    """Start sequence"""
    _check(DMD_api.AlpProjStart( nDevId, nSeqId ))

    """Wait for the sequence to finish displaying"""
    print "Displaying DMD pattern sequence..."
    DMD_api.AlpProjWait( nDevId )
    print " Done."

def free_device(nDevId):
    print "Freeing DMD device %i..."%(nDevId.value)
    _check(DMD_api.AlpDevHalt( nDevId ))
    _check(DMD_api.AlpDevFree( nDevId ))

if __name__ == '__main__':
    device_id = open_dmd()
    sequence_id, num_images = apply_settings(
        device_id, illumination_filename='illumination_pattern.raw')
    display_pattern(device_id, sequence_id)
    free_device(device_id)
