import ctypes
import numpy

try:
    DMD_api = ctypes.cdll.LoadLibrary('alpD41')
    _ALP_DEFAULT = 0
    _ALP_OK = 0
    _ALP_DEV_DMDTYPE = 2021
    _ALP_DMDTYPE_XGA_055X = 6
    _ALP_DATA_FORMAT = 2110
except OSError:
    print '*'*40 + "\n\nFailed to load the DMD API.\n\n" + '*'*40

def _check(return_code):
    if return_code != _ALP_OK:
        raise UserWarning("Failed with return code %i"%(return_code))    

class ALP:
    def __init__(self):
        """Allocate the ALP high-speed device"""
        print "Allocating DMD device..."
        self.id = ctypes.c_ulong()
        try:
            _check(DMD_api.AlpDevAlloc(
                _ALP_DEFAULT, _ALP_DEFAULT, ctypes.byref(self.id)))
        except:
            print "\n\n Failed to allocate the DMD. Is ALP Basic open?\n\n"
            raise
        print " Device ID:", self.id.value
        self.seq_id = None
        return None

    def apply_settings(
        self, illuminate_time, picture_time=4500, trigger_delay=0,
        illumination_filename='illumination_pattern.raw',
        first_frame=None, last_frame=None, repetitions=None,
        additional_preframes=None):
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
        bytes_per_pix = 1
        f = open(illumination_filename, 'rb')
        if first_frame == None: first_frame = 0
        if last_frame == None:
            count = -1
        else:
            count = (1 + last_frame - first_frame)*bytes_per_pix*nSizeX*nSizeY
        f.seek(first_frame * bytes_per_pix * nSizeX * nSizeY)
        illumination_pattern = numpy.fromfile(f, dtype=numpy.uint8, count=count)
        num_frames = illumination_pattern.shape[0] // (nSizeX * nSizeY)
        if num_frames * nSizeX * nSizeY != illumination_pattern.shape[0]:
            raise UserWarning(
                "Illumination pattern should be a stack of %i by %i images"%(
                    nSizeX, nSizeY))
        illumination_pattern = illumination_pattern.reshape(
            num_frames, nSizeY, nSizeX)
        print " Illumination pattern loaded with", num_frames, "frames"
        if repetitions is not None:
            illumination_pattern_r = numpy.zeros(
                (illumination_pattern.shape[0] * repetitions,
                 nSizeY, nSizeX), dtype=numpy.uint8)
            for i in range(repetitions):
                illumination_pattern_r[i:illumination_pattern.shape[0]+i, :, :
                                       ] = illumination_pattern
            illumination_pattern = illumination_pattern_r
        if additional_preframes is not None:
            illumination_pattern_pf = numpy.zeros(
                (illumination_pattern.shape[0] + additional_preframes,
                 nSizeY, nSizeX), dtype=numpy.uint8)
            illumination_pattern_pf[additional_preframes:, :, :
                                    ] = illumination_pattern
            illumination_pattern = illumination_pattern_pf
        num_frames = illumination_pattern.shape[0]
        illumination_pattern = illumination_pattern.reshape(
            illumination_pattern.size)
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

##    def apply_widefield_settings(
##        self, illuminate_time=250, picture_time=4500):
##        if picture_time == 4500 and illuminate_time > 2200:
##            raise UserWarning("illuminate_time is too long.")
##        return self.apply_settings(
##            illumination_filename='widefield_pattern.raw',
##            illuminate_time=illuminate_time, picture_time=picture_time)

    def display_pattern(self, verbose=True):
        """Start sequence"""
        _check(DMD_api.AlpProjStart(self.id, self.seq_id))

        """Wait for the sequence to finish displaying"""
        if verbose:
            print "Displaying DMD pattern sequence..."
        DMD_api.AlpProjWait(self.id)
        if verbose:
            print " Done."

    def close(self):
        print "Freeing DMD device %i..."%(self.id.value)
        _check(DMD_api.AlpDevHalt(self.id))
        _check(DMD_api.AlpDevFree(self.id))

class Micromirror_Subprocess:
    def __init__(
        self, illuminate_time, picture_time=4500, delay=0.01,
        illumination_filename='illumination_pattern.raw',
        first_frame=None, last_frame=None,
        repetitions=None, additional_preframes=None):
        """To synchronize the DMD and the camera polling, we need two
        processes. 'delay' determines how long the DMD subprocess
        waits after a trigger message before displaying a pattern.
        Every time a signal is written to the process with
        proc.stdin.write(), two lines need to be read out with
        proc.stdout.readline()."""
        import subprocess, sys

        cmdString = """
try:
    import dmd, sys, time
    micromirrors = dmd.ALP()
    sys.stdout.flush()
    while True:
        cmd = raw_input()
        if cmd == 'done':
            break
        elif cmd == 'apply_settings':
            illuminate_time = int(raw_input())
            picture_time = int(raw_input())
            illumination_filename = raw_input()
            first_frame = raw_input()
            try:
                first_frame = int(first_frame)
            except ValueError:
                first_frame = None
            last_frame = raw_input()
            try:
                last_frame = int(last_frame)
            except ValueError:
                last_frame = None
            repetitions = raw_input()
            try:
                repetitions = int(repetitions)
            except ValueError:
                repetitions = None
            additional_preframes = raw_input()
            try:
                additional_preframes = int(additional_preframes)
            except ValueError:
                additional_preframes = None
            num_frames = micromirrors.apply_settings(
                illuminate_time=illuminate_time, picture_time=picture_time,
                illumination_filename=illumination_filename,
                first_frame=first_frame, last_frame=last_frame,
                repetitions=repetitions,
                additional_preframes=additional_preframes)
            sys.stdout.write(repr(int(num_frames)) + '\\n')
        else:
            time.sleep(%s) #Give the camera time to arm
            micromirrors.display_pattern()
        sys.stdout.flush()
    micromirrors.close()
except:
    import traceback
    traceback.print_exc()
"""%(repr(delay))
        self.subprocess = subprocess.Popen( #python vs. pythonw on Windows?
            [sys.executable, '-c %s'%cmdString],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        for i in range(2):
            print self.subprocess.stdout.readline(),
        self.apply_settings(illuminate_time=illuminate_time,
                            picture_time=picture_time,
                            illumination_filename=illumination_filename,
                            first_frame=first_frame, last_frame=last_frame)
        return None

    def apply_settings(self, illuminate_time, picture_time=4500, delay=None,
                       illumination_filename='illumination_pattern.raw',
                       first_frame=None, last_frame=None,
                       repetitions=None, additional_preframes=None):
        """delay is ignored, only here so the calling convention
        matches the other 'apply_settings'"""
        self.subprocess.stdin.write('apply_settings\n')
        self.subprocess.stdin.write(repr(illuminate_time) + '\n')
        self.subprocess.stdin.write(repr(picture_time) + '\n')
        self.subprocess.stdin.write(illumination_filename + '\n')
        self.subprocess.stdin.write(repr(first_frame) + '\n')
        self.subprocess.stdin.write(repr(last_frame) + '\n')
        self.subprocess.stdin.write(repr(repetitions) + '\n')
        self.subprocess.stdin.write(repr(additional_preframes) + '\n')
        for i in range(6):
            print self.subprocess.stdout.readline(),
        response = self.subprocess.stdout.readline()
        try:
            self.num_images = int(response)
        except ValueError:
            print response
            print "Subprocess error message:",
            for i in self.subprocess.communicate():
                print ' ', i.replace('\n', '\n ')
            print "\n\nSomething's wrong... is the DMD on and plugged in?"
            print "\n\nI'm looking at you, Temprine!\n\n"
            raise
        if first_frame is not None:
            print "First frame:", first_frame
        if last_frame is not None:
            print "Last frame:", last_frame
        if repetitions is not None:
            print "Repetitions:", repetitions
        if additional_preframes is not None:
            print "Additional preframes:", additional_preframes
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
        illuminate_time=2200, picture_time=4500,
        illumination_filename='widefield_pattern.raw')
    for i in range(3):
        micromirrors.apply_settings(
            illuminate_time=2200, picture_time=4500,
            illumination_filename='illumination_pattern.raw',
            first_frame=3, last_frame=3,
            repetitions=20, additional_preframes=3)
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
