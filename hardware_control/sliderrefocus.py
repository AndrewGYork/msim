import wx
import wx.lib.agw.floatspin as FS

class MyFrame(wx.Frame):
    def __init__(self, parent, id, title):

        wx.Frame.__init__(self, parent, id, title, wx.DefaultPosition, (300, 150))
        panel = wx.Panel(self, -1)

        vbox = wx.BoxSizer(wx.VERTICAL)
        hbox = wx.BoxSizer(wx.HORIZONTAL)

        self.floatspin = FS.FloatSpin(panel, -1, pos=(50, 50), min_val=0, max_val=10,
                                 increment=0.1, value=5, agwStyle=FS.FS_LEFT)
        self.floatspin.SetFormat("%f")
        self.floatspin.SetDigits(2)

        btn1 = wx.Button(panel, 8, 'Adjust')
        btn2 = wx.Button(panel, 9, 'Close')

        wx.EVT_BUTTON(self, 8, self.OnAdjust)
        wx.EVT_BUTTON(self, 9, self.OnClose)
        vbox.Add(self.floatspin, 1, wx.ALIGN_CENTRE)
        hbox.Add(btn1, 1, wx.RIGHT, 10)
        hbox.Add(btn2, 1)
        vbox.Add(hbox, 0, wx.ALIGN_CENTRE | wx.ALL, 20)
        panel.SetSizer(vbox)

    def OnAdjust(self, event):
        self.voltage = self.floatspin.GetValue()
        print self.voltage

        ##set voltage
    def OnClose(self, event):
        self.Close()

class MyApp(wx.App):
    def OnInit(self):
        frame = MyFrame(None, -1, 'Refocus Voltage Adjuster')
        frame.Show(True)
        frame.Centre()
        return True

app = MyApp(0)
app.MainLoop()
