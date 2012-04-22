import serial, time

class Laser_405:
    def __init__(self):
        self.port = {}
        self.state = {}
        try:
            self.port = serial.Serial(9, 19200, timeout=1)
        except:
            raise UserWarning(
                "Can't open port for the 405 nm laser")
        self.no_delay()
        self.get_state(verbose=False)
        self.set_power('max', verbose=False)

    def no_delay(self):
        self.port.write('?CDRH\r')
        response = self.port.readline()
        if response == 'CDRH=1\r\n':
            self.port.write('CDRH=0\r')
            response = self.port.readline()
            if response == 'CDRH=0\r\n': #Great
                return None
            else:
                print response
                raise UserWarning('Failure to disable 405 nm laser CDRH delay')               
        return None
    
    def get_state(self, color='488', verbose=True):
        self.state = {}
        p = self.port
        p.flushInput()
        p.flushOutput()
        p.write("?S\r")
        response = []
        for i in range(8):
            response.append(p.readline())
        for i, (k, name, func) in enumerate((
            ('CDRH','Emission delay', int),
            ('DST', 'Diode temperature setpoint', float),
            ('SP', 'Laser power setpoint', float),
            ('L', 'On/off', int),
            ('T', 'TEC status', int),
            ('CW', 'Continous or pulsed mode', int),
            ('ANA', 'External analog power control', int),
            ('EXT', 'External power control', int)
            )):
            try:
                self.state[name] = func(response[i].split(k+'=')[1])
            except ValueError:
                print "Response not understood:"
                print response
        for k, name, func in ((
            ('MINLP', 'Laser power minimum', float),
            ('MAXLP', 'Laser power maximum', float),
            ('DT', 'Diode temperature (actual)', float),
            )):
            self.port.write('?'+k+'\r')
            self.state[name] = func(self.port.readline().split(k+'=')[1])
            
        if verbose:
            print '405 nm laser status:'
            for k in sorted(self.state.keys()):
                print ' '+k+':', repr(self.state[k])
        return None

    def on(self, verbose=True):
        if verbose:
            print "Turning on 405 nm laser"
        self.port.write('L=1\r')
        response = self.port.readline()
        if response == 'L=1\r\n':
            return None
        else:
            print "Response:", repr(response)
            raise UserWarning('Serial port response not understood' +
                              'while attempting to turn on 405 nm laser')

    def off(self, verbose=True):
        if verbose:
            print "Turning off 405 nm laser"
        self.port.write('L=0\r')
        response = self.port.readline()
        if response == 'L=0\r\n':
            return None
        else:
            print "Response:", repr(response)
            raise UserWarning('Serial port response not understood' +
                              'while attempting to turn off 405 nm laser')

    def set_power(self, power='max', verbose=True):
        if power == 'max':
            power = self.state['Laser power maximum']
        try:
            power = float(power)
        except ValueError:
            raise UserWarning("Laser power must be a number")
        if verbose:
            print "Setting 405 nm laser power to", power, 'mW'
        pmax = self.state['Laser power maximum']
        pmin = self.state['Laser power minimum']
        if power > pmax:
            power = pmax
            print "\n\nWARNING"
            print "405 nm laser power setting is too high. Setting to",
            print pmax, 'mW\n\n'
        elif power < pmin:
            power = pmin
            print "405 nm laser power setting is too low. Setting to",
            print pmin, 'mW\n\n'
        self.port.write('P=%0.2f\r'%(power))
        response = self.port.readline()
        if response == 'P=0.00\r\n':
            return None
        else:
            print "Response:", repr(response)
            raise UserWarning(
                'Serial port response not understood' +
                'while attempting to set power of the 405 nm laser')
        

    def close(self):
        print "Closing 405 nm laser serial port..."
        self.port.close()        

if __name__ == '__main__':
    laser = Laser_405()
    for power in (5, 50, 10, 100, 20):
        laser.set_power(power)
        laser.get_state()
        print "Pulsing..."
        for i in range(10):
            laser.on(verbose=False)
            laser.off(verbose=False)
    laser.close()
