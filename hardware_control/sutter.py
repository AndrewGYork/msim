import time, serial

class Lambda_10_B:
    def __init__(self, read_on_init=True):
        print "Initializing Sutter filter wheel..."
        try:
            self.serial = serial.Serial(3, 9600)
        except serial.SerialException:
            raise UserWarning(
                "Could not open the serial port to the Sutter Lambda 10-B." +
                " Is it on? Is it plugged in? Plug it in! Turn it on!")
        self.serial.write('\xee')
        if read_on_init:
            self.read(2)
            self.init_finished = True
            print "Done initializing filter wheel."
        else:
            self.init_finished = False
        self.wheel_position = 0
        return None

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def move(self, filter_slot=0, speed=1):
        if filter_slot == self.wheel_position:
            print "Filter wheel is already at position", self.wheel_position
            return None
        assert filter_slot in range(10)
        assert speed in range(8)
        if not self.init_finished:
            self.read(2)
            self.init_finished = True
            print "Done initializing filter wheel."
        print "Moving filter wheel to position", filter_slot
        self.serial.write(chr(filter_slot + 16*speed))
        self.read(2)
        self.wheel_position = filter_slot
        return None

    def read(self, num_bytes):
        for i in range(100):
            num_waiting = self.serial.inWaiting()
            if num_waiting == num_bytes:
                break
            time.sleep(0.01)
        else:
            raise UserWarning(
                "The serial port to the Sutter Lambda 10-B" +
                " is on, but it isn't responding as expected.")
        return self.serial.read(num_bytes)

    def close(self):
        self.move()
        self.serial.close()


if __name__ == '__main__':
    with Lambda_10_B() as wheel:
        wheel.move(0)
