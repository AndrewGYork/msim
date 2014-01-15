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

class DAQ_with_queue:
    def __init__(self):
        """
        Expected use pattern:
         Initialize
         Add voltages to the queue on the fly
##         Any time the queue is empty, voltages return to (safe?) defaults
         Stop 'playing'
         Close.
        """
        self.input_queue = mp.Queue()
        self.commands, self.child_commands = mp.Pipe()
        self.child = mp.Process(
            target=DAQ_child_process,
            args=(self.child_commands,
                  self.input_queue),
            name='DAQ')
        self.child.start()
        return None

    def send_voltage(self, voltage):
        self.input_queue.put(voltage)
        print "Sending voltage."
        return None

def DAQ_child_process(commands, input_queue):
    daq = DAQ()
    daq.scan()
    write_this_signal = np.zeros(0)
    write_length = daq.write_length
    write_this_signal_now = daq.default_voltage.copy()
    while True:
        if commands.poll():
            info("Command received")
            cmd, args = commands.recv()
            if cmd == 'quit':
                break
        if write_this_signal.shape[0] == 0:
            try:
                """
                Check the input queue for a bite-sized voltage
                """
                write_this_signal = input_queue.get_nowait()
            except Queue.Empty:
                daq.write_voltage(write_default=True)
        """
        While the amount to be written is bigger than the write length,
        chop off the first bit you can and send that to be written
        then check the amount that remains, repeat
        """
        to_be_written = write_this_signal.shape[0]
        while to_be_written >= write_length:
            write_this_signal_now[:] = write_this_signal[:write_length]
            write_this_signal = write_this_signal[write_length:]
            to_be_written = write_this_signal.shape[0]
            daq.set_voltage(write_this_signal_now, verbose=True)
            daq.write_voltage(verbose=True)
        """
        If your array is now too small, which it should be by this point, 
        keep grabbing stuff and appending it on to the end until you're either 
        too big again, or you run out of stuff to grab
        If you're too big, get kicked out of this loop and the big loop starts
        over again
        If you run out of stuff to grab, write everything you have followed
        by default values, then reset everything so next time around the
        big loop it's a fresh start
        """
        while 0 < to_be_written < write_length:
            try:
                """
                Check the input queue for the next voltage
                """
                append_me = input_queue.get_nowait()
            except Queue.Empty:
                """
                Write the little bit we have followed by default voltages
                """
                write_this_signal_now[:to_be_written] = write_this_signal
                daq.set_voltage(write_this_signal_now, verbose=True)
                daq.write_voltage(verbose=True)
                """                
                Reset write_this_signal to 0 array so next time around
                we get put back in the new scenario, and reset 
                write_this_signal_now to the default array so if we try to do
                this again we actually get the rest defaults
                """
                write_this_signal = np.zeros(0)
                write_this_signal_now[:] = daq.default_voltage
            else:
                write_this_signal = np.concatenate(write_this_signal, 
                                               append_me)
            
            to_be_written = write_this_signal.shape[0]

    daq.stop_scan()
    daq.close()            

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

    def set_voltage(self, voltage, verbose=False):
        assert self.voltage.shape == voltage.shape
        self.voltage[:] = voltage
        if verbose:
            print "Voltage set."
        return None

    def write_voltage(self, write_default=False, verbose=False):
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
        if verbose:
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
    """
    Test basic functionality of the DAQ object
    """
##    daq = DAQ()
##    daq.scan()
##    while True:
##        try:
##            daq.write_voltage()
##        except KeyboardInterrupt:
##            break
##    """
##    Test basic functionality of the 'DAQ_child_process' function
##    """
##    input_queue = mp.Queue()
##    commands, child_commands = mp.Pipe()
##    print "Press Ctrl-C to exit..."
##    try:
##        DAQ_child_process(commands, input_queue)
##    except KeyboardInterrupt:
##        pass
##    print "Done."

    """
    Test basic functionality of the 'DAQ_with_queue' object
    """
    daq = DAQ_with_queue()
    print "Waiting a bit..."
    time.sleep(2)
    print "Sending signal..."
    sig = np.zeros((10000, 8), dtype=np.float64)
    daq.send_voltage(sig)
    print "Done sending."

    print "Waiting a bit..."
    time.sleep(2)
    print "Sending several small signals..."
    sig1 = np.ones((2500, 8), dtype=np.float64)
    sig2 = 0.75 * np.ones((2500, 8), dtype=np.float64)
    sig3 = 0.5 * np.ones((2500, 8), dtype=np.float64)
    sig4 = 0.25 * np.ones((2500, 8), dtype=np.float64)
    daq.send_voltage(sig1)
    daq.send_voltage(sig2)
    daq.send_voltage(sig3)
    daq.send_voltage(sig4)
    print "Done sending."
    
    print "Waiting a bit..."
    time.sleep(2)
    print "Sending a too big signal..."
    sig = 0.5 * np.ones((25000, 8), dtype=np.float64)
    daq.send_voltage(sig)
    print "Done sending."
    
    print "Waiting a bit..."
    time.sleep(2)
    print "Sending signal..."
    sig = 0 * np.ones((10000, 8), dtype=np.float64)
    daq.send_voltage(sig)
    print "Done sending."
        
