import time
import sys
import ctypes
import warnings
import Queue
import multiprocessing as mp
import numpy as np

"""
Requires nicaiu.dll to be in the same directory, or located in the
os.environ['PATH'] search path.

If you get an error, read NIDAQmx.h to decypher it.
"""

api = ctypes.cdll.LoadLibrary("nicaiu")
log = mp.get_logger()
info = log.info
debug = log.debug
if sys.platform == 'win32':
    clock = time.clock
else:
    clock = time.time

##class DAQ_with_queue:
##    def __init__(self):
##        """
##        Expected use pattern:
##         Initialize
##         Add voltages to the queue
##         Start 'playing' the voltages in the queue
##         Add voltages to the queue on the fly
##         Any time the queue is empty, voltages return to (safe?) defaults
##         Stop 'playing'
##         Close.
##        """
##        self.input_queue = mp.Queue()
##        self.commands, self.child_commands = mp.Pipe()
##        self.child = mp.Process(
##            target=DAQ_child_process,
##            args=(self.child_commands,
##                  self.input_queue),
##            name='DAQ')
##        self.child.start()
##        return None
##
##def DAQ_child_process(commands, input_queue):
##    daq = DAQ()
##    on_deck = None
##    on_deck_pointer = None
##    while True:
##        if commands.poll():
##            info("Command received")
##            cmd, args = commands.recv()
##            if cmd == 'quit':
##                break
##        try:
##            """
##            Check the internal queue for a bite-sized voltage
##            """
##            write_this_signal = internal_queue.get_nowait()
##            daq.
            

class DAQ:
    def __init__(
        self,
        num_channels=8,
        default_voltage=None,
        rate=1e5,
        regenerate=False,
        write_length=10000,
        ):
        print "Opening DAQ card..."
        print "DAQ card open."
        if default_voltage == None:
            default_voltage = [0 for i in range(num_channels)]
        else:
            assert len(default_voltage) == num_channels
        self.default_voltage = np.zeros(
            (write_length, num_channels), dtype=np.float64)
        for i, v in enumerate(default_voltage):
            self.default_voltage[:, i].fill(v)
        self.voltage = self.default_voltage.copy()
        self.write_length = write_length
        self.num_channels = num_channels
        self.taskHandle = ctypes.c_void_p(0)
        self.num_points_written = ctypes.c_ulong(0)

        DAQmxErrChk(api.DAQmxCreateTask("", ctypes.byref(self.taskHandle)))
        DAQmxErrChk(api.DAQmxCreateAOVoltageChan(
            self.taskHandle,
            "Dev1/ao0:%i"%(self.num_channels - 1),
            "",
            ctypes.c_double(-10.0), #Minimum voltage
            ctypes.c_double(10.0), #Maximum voltage
            10348, #DAQmx_Val_Volts; don't question it!
            ctypes.c_void_p(0), #NULL
            ))
        print "DAQ initialized"

        self.set_rate(rate)
        self.set_regeneration(regenerate)
        self.set_output_buffer_size(2 * write_length)
        self.write_voltage()
        self.write_voltage()
        return None

    def set_rate(self, rate):
        self.rate = rate
        DAQmxErrChk(api.DAQmxCfgSampClkTiming(
            self.taskHandle,
            ctypes.c_void_p(0),#NULL, to specify onboard clock for timing
            ctypes.c_double(self.rate),
            10280, #DAQmx_Val_Rising, doesn't matter
            10123, #DAQmx_Val_ContSamps (Run continuous)
            2 * self.write_length))
        print "DAQ card scan rate set to", self.rate, "points per second"
        return None

    def set_regeneration(self, allow=True):
        """
        Disable signal regeneration
        """
        if allow:
            val = 10097 #DAQmx_Val_AllowRegen
        else:
            val = 10158 #DAQmx_Val_DoNotAllowRegen
        DAQmxErrChk(api.DAQmxSetWriteAttribute(
            self.taskHandle,
            5203, #DAQmx_Write_RegenMode
            val,
            ))
        print "DAQ card regeneration mode set to:", allow
        return None

    def set_output_buffer_size(self, size):
        DAQmxErrChk(api.DAQmxCfgOutputBuffer(self.taskHandle, size))
        print "DAQ output buffer enlarged to:", size
        return None

    def write_voltage(self, write_default=False):
        if write_default:
            voltage = self.default_voltage
        else:
            voltage = self.voltage
        DAQmxErrChk(api.DAQmxWriteAnalogF64(
            self.taskHandle,
            self.write_length,
            0,
            ctypes.c_double(10.0), #Timeout for writing.
            1, #DAQmx_Val_GroupByScanNumber (interleaved)
            np.ctypeslib.as_ctypes(voltage),
            ctypes.byref(self.num_points_written),
            ctypes.c_void_p(0)
            ))
        print self.num_points_written.value,
        print "points written to each DAQ channel."
        return None

    def scan(self):
        print "Scanning voltage..."
        DAQmxErrChk(api.DAQmxStartTask(self.taskHandle))
        return None

    def stop_scan(self):
        DAQmxErrChk(api.DAQmxStopTask(self.taskHandle))
        print "Done scanning"
        return None

    def close(self):
        DAQmxErrChk(api.DAQmxClearTask(self.taskHandle))
        return None

def DAQmxErrChk(err_code):
    if err_code != 0:
        num_bytes = api.DAQmxGetExtendedErrorInfo(ctypes.c_void_p(0), 0)
        print "Error message from NI DAQ: (", num_bytes, "bytes )"
        errBuff = np.ctypeslib.as_ctypes(
            np.zeros(num_bytes, dtype=np.byte))
        api.DAQmxGetExtendedErrorInfo(errBuff, num_bytes)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            print np.ctypeslib.as_array(errBuff).tostring()
        raise UserWarning("NI DAQ error code: %i"%(err_code))

if __name__ == '__main__':
    daq = DAQ()
    daq.scan()
    while True:
        try:
            daq.write_voltage()
        except KeyboardInterrupt:
            break
        
