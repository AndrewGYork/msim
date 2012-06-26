import serial

class AOTF:
    def __init__(self):
        try:
            self.ser = serial.Serial(port=3) #Have to pick the right port
        except:
            raise UserWarning("Can't open the gooch")
        for i in range(8):
            self.set_amplitude(channel=i+1, amplitude=0)
            self.off(channel=i+1)
        self.set_frequency(channel=1, frequency=115.5)
####  Channel 1 is the 405nm channel
        self.set_frequency(channel=2, frequency=86.55)
        self.set_amplitude(channel=2, amplitude=1023)
        self.on(channel=2)
####  Channel 2 is the 488nm channel
        return None


    def set_frequency(self, channel, frequency):
##        assert(channel == 1 or channel == 2 or channel == 3)
##        try:
##            channel = int(channel)
##        except ValueError:
##            raise UserWarning("'channel' has to be an integer, jackass")
        self.ser.write('ch%i\r\n'%(channel))
        self.ser.write('fr %0.3f\r\n'%(frequency))
        return None

    def set_amplitude(self, channel, amplitude):
        self.ser.write('ch%i\r\n'%(channel))
        self.ser.write('am %i\r\n'%(amplitude))
        return None

    def on(self, channel):
        self.ser.write('ch%i\r\n'%(channel))
        self.ser.write('on\r\n')
        return None

    def off(self, channel=0):
        self.ser.write('ch%i\r\n'%(channel))
        self.ser.write('off\r\n')
        return None

    def flushbuffers(self):
        self.ser.flush(self)
        self.ser.flushInput(self)
        self.ser.flushOutput(self)
        return None
    
    def close(self):
##        self.set_amplitude(channel=0, amplitude=0)
        self.set_frequency(channel=2, frequency=86.55)
        self.set_amplitude(channel=2, amplitude=1023)
        self.on(channel=2)
        self.ser.close()
        return None

if __name__ == '__main__':
    import time
    a = AOTF()
    a.off(channel=2)
    time.sleep(2)
##    a.set_amplitude(channel=1, amplitude=10)
##    a.set_frequency(channel=1, frequency=86.55)
##    a.on(channel=1)
##
##    for i in range(800, 900):
##        print i
##        a.set_frequency(channel=1, frequency=i*0.1)
##        time.sleep(.01)
    a.close()
