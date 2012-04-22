import serial, time

class Filter_Wheel:
    def __init__(self, initial_position='f3', wheel_delay=1.8):
        try:
            self.ser = serial.Serial(7, 115200) #Have to pick the right port
        except:
            raise UserWarning(
                "Can't open port for the filter wheel.")
        self.position = None
        self.wheel_delay=wheel_delay
        self.move(initial_position)
        return None

    def move(self, new_position='f3'):
        if new_position == self.position:
            return None
        position = int(new_position.replace('f', ''))
        print "Moving filter wheel to %i"%(position)
        self.ser.write("pos=%i\r"%(position))
        time.sleep(self.wheel_delay)
        self.position = new_position
        return None

    def close(self):
        self.move('f3')
        self.ser.close()             # close port
        return None

if __name__ == '__main__':
    f = Filter_Wheel()
    f.move(new_position='f1')
    f.move(new_position='f2')
    f.close()
