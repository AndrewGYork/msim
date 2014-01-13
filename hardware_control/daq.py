import time
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

log = mp.get_logger()
info = log.info
debug = log.debug
if sys.platform == 'win32':
    clock = time.clock
else:
    clock = time.time

##class DAQ_with_queue:
##    def __init__(self):
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
        buffer_length=10000,
        num_channels=8,
        default_voltage=None,
        rate=1e5,
        regenerate
        ):
        """
        Expected use pattern:
         Initialize
         Add voltages to the queue
         Start 'playing' the voltages in the queue
         Add voltages to the queue on the fly
         Any time the queue is empty, voltages return to (safe?) defaults
         Stop 'playing'
         Close.
        """
        print "Opening DAQ card..."
        api = ctypes.cdll.LoadLibrary("nicaiu")
        print "DAQ card open."
        if default_voltage == None:
            default_voltage = [0 for i in range(num_channels)]
        self.default_voltage = numpy.zeros(
            (buffer_length, num_channels), dtype=numpy.float64)
        for i, v in enumerate(default_voltage):
            self.default_voltage[:, i].fill(v)
        self.voltage = self.default_voltage.copy()
        self.voltage_queue = []
        self.voltage_queue_bookmark = 0
        self.buffer_length = buffer_length
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

        self.set_rate(5e5)
        self.set_regeneration(False)
        self.register_callback_for_every_n_samples()
        self.set_output_buffer_size(2*buffer_length)
        self.write_voltage()
        self.write_voltage()
        return None
