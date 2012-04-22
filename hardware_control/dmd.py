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

class ALP:
    def __init__(self):
        """Allocate the ALP high-speed device"""
        print "Allocating DMD device..."
        self.id = ctypes.c_ulong()
        _check(DMD_api.AlpDevAlloc(
            _ALP_DEFAULT, _ALP_DEFAULT, ctypes.byref(self.id)))
        print " Device ID:", self.id.value
        self.seq_id = None
        return None

    def apply_settings(
        self, illumination_filename='illumination_pattern.raw',
        illuminate_time=2200, picture_time=4500, trigger_delay=0):
        """illuminate_time, picture_time, and trigger_delay are in
        microseconds

        """

        print "Applying settings to DMD..."
        if self.seq_id is not None:
            _check(DMD_api.AlpSeqFree(self.id, self.seq_id))
            self.seq_id = None
        """Check the DMD type"""
        nDmdType = ctypes.c_long()
        _check(DMD_api.AlpDevInquire(
            self.id, _ALP_DEV_DMDTYPE, ctypes.byref(nDmdType)))
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
        self.seq_id = ctypes.c_ulong()
        _check(DMD_api.AlpSeqAlloc(
            self.id, 1, num_frames, ctypes.byref(self.seq_id)))
        print " Sequence ID:", self.seq_id.value

        """Transmit images into ALP memory"""
        _check(DMD_api.AlpSeqPut(
            self.id, self.seq_id, 0, num_frames, illumination_pattern_c ))
        print " Images transmitted."

        """Set up image timing
        For highest frame rate, first switch to binary uninterrupted mode
        (_ALP_BIN_UNINTERRUPTED) by using AlpDevControl. See also the release
        notes for more details."""
        _check(DMD_api.AlpSeqTiming(
            self.id, self.seq_id,
            int(illuminate_time), int(picture_time), int(trigger_delay),
            _ALP_DEFAULT, _ALP_DEFAULT ))

        paramVal = ctypes.c_long()	
        _check(DMD_api.AlpSeqInquire(
            self.id, self.seq_id, _ALP_DATA_FORMAT, ctypes.byref(paramVal)))
        print " ALP data format:", paramVal.value
        return num_frames

    def apply_widefield_settings(
        self, illuminate_time=250, picture_time=4500):
        if picture_time == 4500 and illuminate_time > 2200:
            raise UserWarning("illuminate_time is too long.")
        return self.apply_settings(
            illumination_filename='widefield_pattern.raw',
            illuminate_time=illuminate_time, picture_time=picture_time)

    def display_pattern(self):
        """Start sequence"""
        _check(DMD_api.AlpProjStart(self.id, self.seq_id))

        """Wait for the sequence to finish displaying"""
        print "Displaying DMD pattern sequence..."
        DMD_api.AlpProjWait(self.id)
        print " Done."

    def close(self):
        print "Freeing DMD device %i..."%(self.id.value)
        _check(DMD_api.AlpDevHalt(self.id))
        _check(DMD_api.AlpDevFree(self.id))

class Micromirror_Subprocess:
    def __init__(
        self, delay=0.01,
        illuminate_time=None, picture_time=4500,
        pattern='sim'):
        """To synchronize the DMD and the camera polling, we need two
        processes. 'delay' determines how long the DMD subprocess
        waits after a trigger message before displaying a pattern.
        Every time a signal is written to the process with
        proc.stdin.write(), two lines need to be read out with
        proc.stdout.readline()."""
        import subprocess, sys

        if illuminate_time is None:
            if pattern == 'sim':
                illuminate_time = 2200
            if pattern == 'widefield':
                illuminate_time = 250

        cmdString = """
import dmd, sys, time
micromirrors = dmd.ALP()
num_frames = %s
sys.stdout.write(repr(int(num_frames)) + '\\n')
while True:
    sys.stdout.flush()
    cmd = raw_input()
    if cmd == 'done':
        break
    time.sleep(%s) #Give the camera time to arm
    micromirrors.display_pattern()
micromirrors.close()
"""%({'sim': 'micromirrors.apply_settings',
      'widefield': 'micromirrors.apply_widefield_settings'}[pattern] +
     '(illuminate_time=%i, picture_time=%i,)'%(illuminate_time, picture_time),
     repr(delay))
        self.subprocess = subprocess.Popen( #python vs. pythonw on Windows?
            [sys.executable, '-c %s'%cmdString],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        for i in range(8):
            print self.subprocess.stdout.readline(),
        try:
            self.num_images = int(self.subprocess.stdout.readline())
        except ValueError:
            print "\n\nSomething's wrong... is the DMD on and plugged in?\n\n"
            print "\n\nI'm looking at you, Temprine!\n\n"
            raise
        print "Num. images:", self.num_images
        return None
    
    def display_pattern(self):
        """Must be followed with readout() to prevent filling the pipe buffer"""
        self.subprocess.stdin.write('Go!\n')

    def readout(self):
        """Call this once after each time you call display_pattern()"""
        for i in range(2):
            print '*', self.subprocess.stdout.readline(),

    def close(self):
        try:
            self.subprocess.stdin.write('done\n')
        finally:
            report = self.subprocess.communicate()
            for i in report:
                print i
            return None

if __name__ == '__main__':
    print "Creating a micromirror subprocess..."
    micromirrors = Micromirror_Subprocess(
        illuminate_time=6700, picture_time=20000)
    micromirrors.display_pattern()
    micromirrors.readout()
    micromirrors.close()

##    print "Creating a widefield micromirror subprocess..."
##    micromirrors = Micromirror_Subprocess(pattern='widefield')
##    for i in range(10):
##        micromirrors.display_pattern()
##        micromirrors.readout()
##    micromirrors.close()

##    print "Checking micromirror timing..."
##    import time, numpy, pylab
##    dmd = ALP()
##    dmd.apply_settings(illumination_filename='illumination_pattern.raw')
##    times = []
##    for i in range(50):
##        times.append(time.clock())
##        dmd.display_pattern()
##    dmd.close()
##    fig = pylab.figure()
##    pylab.plot(numpy.diff(times), '.-')
##    fig.show()
##    fig.canvas.draw()
