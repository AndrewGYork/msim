import serial, time

class Laser_Shutters:
    def __init__(self):
        self.ports = {}
        self.states = {}
        self.ports['488'] = serial.Serial(4, 9600, timeout=1)
        self.ports['561'] = serial.Serial(5, 9600, timeout=1)
        for c in self.ports.keys():
            self._robust_shut(c)
            self.states[c] = False
         #Have to pick the right ports

    def toggle(self, color='488', verbose=True): #Fast but not robust
        if verbose: print "Toggling shutter:", color
        p = self.ports[color]
        p.write("ens\r")
        while p.inWaiting() < 6:
            time.sleep(0.001)
        response = p.read(p.inWaiting())
        if response != 'ens\r> ':
            raise UserWarning("Shutter state not understood.")
        self.states[color] = not self.states[color]

    def get_state(self, color='488'):
        p = self.ports[color]
        p.flushInput()
        p.flushOutput()
        p.write("ens?\r")
        while p.inWaiting() < 9:
            time.sleep(0.001)
        response = p.read(p.inWaiting())
        if response == 'ens?\r0\r> ':
            return False
        elif response == 'ens?\r1\r> ':
            return True
        else:
            raise UserWarning("Shutter state not understood.")

    def open(self, color='488'):
        print "Opening shutter:", color
        if self.states[color]:
            pass
        else:
            self.toggle(color, verbose=False)

    def shut(self, color='488'):
        print "Shutting shutter:", color
        if self.states[color]:
            self.toggle(color, verbose=False)
        else:
            pass

    def _robust_shut(self, color='488'): #Slower but more reliable
        print "Ensuring shutter is shut:", color
        if self.get_state(color):
            p = self.ports[color]
            p.flushInput()
            p.flushOutput()
            p.write("ens\r")
            while p.inWaiting() < 6:
                time.sleep(0.001)
            response = p.read(p.inWaiting())
            if response != 'ens\r> ':
                raise UserWarning("Shutter state not understood.")
            self.states[color] = False
        else:
            pass

    def close(self):
        print "Closing shutters and shutter ports..."
        for c, p in self.ports.items():
            self._robust_shut(c)
            p.close()        

if __name__ == '__main__':
    import time
    try:
        s = Laser_Shutters()
        s.open(color='488')
        time.sleep(1)
        s.shut(color='488')
        time.sleep(1)
        s.open(color='561')
        time.sleep(1)
        s.shut(color='561')
        time.sleep(1)
        s.open(color='488')
        s.open(color='561')
        time.sleep(1)
        s.shut(color='488')
        s.shut(color='561')
    except:
        print "\nHm, something went wrong, better close the shutters...\n"
        raise
    finally:
        s.close()
