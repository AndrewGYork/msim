import serial

class XYZ:
    def __init__(self):
        print "Initializing xyz stage..."
        self.ser = serial.Serial(0, 9600) #Have to pick the right port
        print "Done initializing."
        self.messages = []

    def move_z(self, pos=0.00):
        print "Moving piezo stage to %0.2f"%(zPos)
        self.send("move z=%0.2f"%(zPos))      # write a string

    def move_xy(self, x=0.00, y=0.00):
        print "Moving XY stage to %0.3f, 0.03f"%(x, y)
        self.send("move x=%0.2f, y=%0.2f"%(x, y))      # write a string

    def get_stage_position(self):
        self.send('where x y z')
        response = self.ser.readline()
        try:
            ok, x, y, z = response.split()
        except ValueError:
            raise UserWarning("Unexpected response from stage:\n" +
                              response)
        assert ok == ':A'
        try:
            x = 0.1 * int(x)
            y = 0.1 * int(y)
            z = 0.1 * int(z)
        except ValueError:
            raise UserWarning("XYZ Stage reported position not understood")
        return (x, y, z)

    def set_piezo_control(self, mode='knob'):
        print "Setting piezo control mode to:", mode
        if mode == 'knob':
            self.send('pz z=0')
        elif mode == 'external_voltage':
            self.send('pz z=1')
        else:
            raise UserWarning('XYZ stage piezo mode setting not understood')
        return None

    def set_piezo_knob_speed(self, speed=1):
        print "Setting piezo knob speed to:", speed
        self.send('jsspd z=%0.2f'%(speed))
        return None

    def send(self, message):
        if self.ser.inWaiting() > 0:
            self.messages.append(self.ser.read(self.ser.inWaiting()))
        self.ser.write(message + "\r")

    def read(self):
        return self.ser.read(self.ser.inWaiting())

    def close(self):
##        self.move(0)
        self.ser.close()             # close port

if __name__ == '__main__':
    import time
    stage = XYZ()
    stage.set_piezo_knob_speed(20)
    print "Waiting for response..."
    time.sleep(0.5)
    print stage.read()
    print stage.read()
    stage.close()
