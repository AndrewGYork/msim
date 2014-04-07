import time
import numpy as np
import wx
import wx.lib.agw.floatspin as FS
from daq import DAQ

class MyFrame(wx.Frame):
    def __init__(self, parent, id, title):
        wx.Frame.__init__(
            self, parent, id, title, wx.DefaultPosition, (300, 150))
        self.panel = wx.Panel(self, -1)

        vbox = wx.BoxSizer(wx.VERTICAL)
        hbox = wx.BoxSizer(wx.HORIZONTAL)

        self.floatspin = FS.FloatSpin(
            self.panel, -1, pos=(50, 50), min_val=0, max_val=10,
            increment=0.1, value=5, agwStyle=FS.FS_CENTRE)
        self.floatspin.SetFormat("%f")
        self.floatspin.SetDigits(2)

        btn1 = wx.Button(self.panel, 8, 'Adjust')
        btn2 = wx.Button(self.panel, 9, 'Close')

        self.Bind(wx.EVT_CLOSE, self.OnClose)
        btn1.Bind(wx.EVT_BUTTON, self.on_adjust)
        btn2.Bind(wx.EVT_BUTTON, self.OnClose)
        
        vbox.Add(self.floatspin, 1, wx.ALIGN_CENTRE | wx.ALL, 10)
        hbox.Add(btn1, 1, wx.RIGHT, 10)
        hbox.Add(btn2, 1)
        vbox.Add(hbox, 0, wx.ALIGN_CENTRE | wx.ALL, 10)
        self.panel.SetSizer(vbox)
        self.initialize_daq()

    def on_adjust(self, event):
        change_voltage = self.floatspin.GetValue()
        print change_voltage
        self.daq.voltage[:, 2] = change_voltage
        print self.daq.voltage[:, 2]
    def OnClose(self, event):
        self.daq_timer.Stop()
        self.daq.stop_scan()
        self.daq.close()
        print "DAQ Closing"
        self.Destroy()

    def on_daq_timer(self, event):
        this_time = time.clock()
        print "Interval:", this_time - self.last_daq_time
        self.last_daq_time = this_time
        self.daq.write_voltage()

    def initialize_daq(self):
        rotations_per_second = 150
        facets_per_rotation = 10
        points_per_second = 500000

        """
        This logic assumes we can get away with an integer number of
        triggers per write; if we end up using a mirror with an odd
        number of sides, or if the mirror isn't perfectly regular, we
        might have to always use an integer number of rotations per
        write, not an integer number of triggers per write.
        """
        triggers_per_rotation = 2
        triggers_per_second = triggers_per_rotation * rotations_per_second
        points_per_trigger = points_per_second * (1.0 / triggers_per_second)
        facets_per_second = rotations_per_second * facets_per_rotation
        points_per_facet = points_per_second * (1.0 / facets_per_second)
        print
        print "Desired points per rotation:",
        print points_per_trigger * triggers_per_rotation
        print "Desired points per facet:", points_per_facet
        points_per_facet = int(round(points_per_facet))
        points_per_trigger = int(points_per_facet *
                                 facets_per_rotation *
                                 (1.0 / triggers_per_rotation))
        print "Actual points per rotation:",
        print points_per_trigger * triggers_per_rotation
        print "Actual points per facet:", (points_per_trigger *
                                           triggers_per_rotation *
                                           (1.0 / facets_per_rotation))
        print
        print "Desired rotations per second:", rotations_per_second
        rotations_per_second = (
            points_per_second *
            (1.0 / (points_per_trigger * triggers_per_rotation)))
        print "Actual rotations per second:", rotations_per_second
        print 
        points_per_write = points_per_second // 3
        print "Desired write length:", points_per_write
        rotations_per_write = points_per_write * 1.0 / (points_per_trigger *
                                                        triggers_per_rotation)
        rotations_per_write = int(round(rotations_per_write))
        points_per_write = (points_per_trigger *
                            triggers_per_rotation *
                            rotations_per_write)
        print "Actual write length:", points_per_write
        print "Rotations per write:", rotations_per_write
        triggers_per_write = triggers_per_rotation * rotations_per_write
        print "Triggers per write:", triggers_per_write
        print
        self.daq = DAQ(rate=points_per_second, write_length=points_per_write)

        wheel_signal = np.zeros(self.daq.write_length, dtype=np.float64)
        for i in range(triggers_per_write):
            start = i * points_per_trigger
            stop = start + points_per_trigger // 2
            wheel_signal[start:stop] = 6
        wheel_brake_signal = np.zeros(self.daq.write_length, dtype=np.float64)

        laser_signal = np.zeros(self.daq.write_length, dtype=np.float64)
        laser_duration = 1
        print "Laser duration:", laser_duration * 1.0 / points_per_second,
        print "seconds"
        ##Positive is up
        laser_lag = 65
        for i in range(rotations_per_write):
            for n in range(1):
                start = (i * points_per_trigger * triggers_per_rotation +
                         n * points_per_facet + 
                         laser_lag)
                stop = start + laser_duration
                laser_signal[start:stop] = 10

        voltage = np.zeros_like(self.daq.voltage)
        voltage[:, 0] = wheel_signal
        voltage[:, 1] = wheel_brake_signal
        voltage[:, 2] = 5 #focusing objective
        voltage[:, 3] = 0 #murrrcle
        voltage[:, 6] = laser_signal
        voltage[:, 7] = laser_signal
        self.daq.set_voltage(voltage)
        self.seconds_per_write = self.daq.write_length * 1.0 / self.daq.rate
        print "Seconds per write:", self.seconds_per_write

        TIMER_ID = 100
        self.daq_timer = wx.Timer(self.panel, TIMER_ID)
        self.daq_timer.Start(round(self.seconds_per_write * 1000 * 0.95))
        wx.EVT_TIMER(self.panel, TIMER_ID, self.on_daq_timer)
        self.last_daq_time = 0
        self.daq.scan()

class MyApp(wx.App):
    def OnInit(self):
        frame = MyFrame(None, -1, 'Refocus Voltage Adjuster')
        frame.Show(True)
        frame.Centre()
        return True

app = MyApp(0)
app.MainLoop()
print "Done"
