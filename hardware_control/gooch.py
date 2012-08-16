import serial

class AOTF:
    def __init__(self):
        print 'initializing the AOTF'
        try:
            self.ser = serial.Serial(port=3) #Have to pick the right port
        except:
            raise UserWarning("Can't open the gooch. Is it on?")
        for i in range(8):
            self.set_amplitude(color=i+1, amplitude=0, verbose=False)
            self.off(color=i+1, verbose=False)
        self.set_frequency(color=1, frequency=116.1)
        self.set_amplitude(color=1, amplitude=1023, verbose=False)
        self.on(color='405', verbose=False)
        self.set_frequency(color=2, frequency=87.69)
        self.set_amplitude(color=2, amplitude=1023, verbose=False)
        self.on(color='488', verbose=False)
        """
        The Gooch has 8 channels
        Channel=1 is the 405nm laser channel
        Channel=2 is the 488nm laser channel
        """
        print 'AOTF is cracking'
        return None

    def color_to_channel(self, color):
        if color == '488':
            return 2
        elif color == '405':
            return 1
        elif color == 'all':
            return 0
        else:
            try:
                channel = int(color)
                assert channel in range(9)
                return channel
            except:
                print "AOTF color not understood"
                print color
                raise
    
    def set_frequency(self, color, frequency):
        channel=self.color_to_channel(color)
        self.ser.write('ch%i\r\n'%(channel))
        self.ser.write('fr %0.3f\r\n'%(frequency))
        return None

    def set_amplitude(self, color, amplitude, verbose=True):
        if verbose:
            print 'Setting the amplitude of the', color,
            print 'channel of the AOTF to', amplitude
        channel=self.color_to_channel(color)
        self.ser.write('ch%i\r\n'%(channel))
        self.ser.write('am %i\r\n'%(amplitude))
        return None

    def on(self, color, verbose=True):
        if verbose:
            print 'Turning on the', color,  'channel of the AOTF'
        channel=self.color_to_channel(color)
        self.ser.write('ch%i\r\n'%(channel))
        self.ser.write('on\r\n')
        return None

    def off(self, color, verbose=True):
        if verbose:
            print 'Turning off the', color,  'channel of the AOTF'
        channel=self.color_to_channel(color)
        self.ser.write('ch%i\r\n'%(channel))
        self.ser.write('off\r\n')
        return None

##    def off_global(self, color=0):
##        self.ser.write('ch%i\r\n'%(channel))
##        self.ser.write('off\r\n')
##        return None

    def flushbuffers(self):
        self.ser.flush(self)
        self.ser.flushInput(self)
        self.ser.flushOutput(self)
        return None
    
    def close(self):
        self.set_amplitude('all', amplitude=0, verbose=False)
        self.set_frequency('488', frequency=87.69)
        self.set_amplitude('488', amplitude=1023, verbose=False)
        self.on(color='488', verbose=False)
        self.set_frequency('405', frequency=116.1)
        self.set_amplitude('405', amplitude=1023, verbose=False)
        self.on(color='405', verbose=False)
        self.ser.close()
        print 'AOTF is now closed'
        return None

if __name__ == '__main__':
##    import time
    a = AOTF()
##    a.off('488')
####    time.sleep(2)
####    a.set_amplitude(channel=1, amplitude=1023)
####    a.set_frequency(channel=1, frequency=116.1)
##    a.off('488')
##
##    for i in range(1130, 1190):
##        print i
##        a.set_frequency(channel=1, frequency=i*0.1)
##        time.sleep(1)
##    a.on('488')
    a.close()