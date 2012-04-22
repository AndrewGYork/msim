import serial, time

class Laser_Shutters:
    def __init__(self, colors='all'):
        self.ports = {}
        self.states = {}
        if colors == 'all':
            colors = ['405', '488', '561']
        for c, p in ( #Have to pick the right ports
            ('405', 8),
            ('488', 4),
            ('561', 5)):
            if c in colors:
                try:
                    self.ports[c] = serial.Serial(p, 9600, timeout=1)
                except:
                    raise UserWarning(
                        "Can't open port for the " + c + " shutter.")
        for c in sorted(self.ports.keys()):
            self._robust_shut(c)
            self.states[c] = False

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
        num_sleeps = 0
        while p.inWaiting() < 9:
            time.sleep(0.001)
            num_sleeps += 1
            if num_sleeps > 1000:
                import sys
                sys.stdout.write(
                    color + " shutter is not responding. (Ctrl-C to abort)\n")
                sys.stdout.flush()
                num_sleeps = 0
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
        for c, p in sorted(self.ports.items()):
            self._robust_shut(c)
            p.close()        

if __name__ == '__main__':
    try:
        s = Laser_Shutters()
        s.open(color='405')
        time.sleep(1)
        s.shut(color='405')
        time.sleep(1)
        s.open(color='488')
        time.sleep(1)
        s.shut(color='488')
        time.sleep(1)
        s.open(color='561')
        time.sleep(1)
        s.shut(color='561')
        time.sleep(1)
        s.open(color='405')
        s.open(color='488')
        s.open(color='561')
        time.sleep(1)
        s.shut(color='405')
        s.shut(color='488')
        s.shut(color='561')
    except:
        print "\nHm, something went wrong, better close the shutters...\n"
        raise
    finally:
        s.close()
