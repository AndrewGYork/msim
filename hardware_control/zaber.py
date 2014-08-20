import time
import serial

class Stage:
    """Zaber stage, attached through the serial port."""
    def __init__(self, timeout=1):
        try:
            self.serial = serial.Serial(
            port=0,
            baudrate=9600,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=timeout)
        except serial.serialutil.SerialException:
            print "Failed to open serial port for Zaber stage."
            print "Sometimes Windows is weird about this!"
            print "Consider trying again."
            raise
        print "Renumbering stages:"
        self.devices = self.renumber_all_devices() 
        for d in self.devices:
            print ' Axis:', d
        print "Done renumbering."
        self.pending_moves = 0
        self.move_home()

    def send(self, instruction):
        """
        send instruction
        'instruction' must be a list of 6 bytes (no error checking)
        """
        for i in instruction:
            self.serial.write(chr(i))
        return None

    def receive(self):
        """
        return 6 bytes from the receive buffer
        there must be 6 bytes to receive (no error checking)
        """
        r = [0, 0, 0, 0, 0, 0]
        try:
            for i in range(6):
                r[i] = ord(self.serial.read(1))
            return r
        except TypeError:
            raise UserWarning(
            "Zaber stage failed to respond. Is the timeout too short?" +
            " Is the stage plugged in?")

    def move(self, distance, movetype='absolute', response=True, axis='all'):
        """
        Sanity checking:
        """
        assert self.pending_moves == 0
        if axis == 'all':
            axis = 0
        axis = int(axis)
        assert 0 <= axis <= len(self.devices)
        if movetype == 'absolute':
            instruction = [axis, 20]
        elif movetype == 'relative':
            instruction = [axis, 21]
        else:
            raise UserWarning("Move type must be 'relative' or 'absolute'")
        """ 
        Data conversion and transfer:
        """
        instruction.extend(four_byte_representation(distance))
        self.send(instruction)
        if axis == 0:
            self.pending_moves = len(self.devices)
        else:
            self.pending_moves = 1
        """
        Possibly, cleanup:
        """
        if response:
            return self.finish_moving()
        return None

    def finish_moving(self):
        response = []
        for r in range(self.pending_moves):
            response.append(self.receive())
        self.pending_moves = 0
        return response

    def set_target_speed(self, speed, response=True):
        inst = [0, 42]
        inst.extend(four_byte_representation(speed))
        self.send(inst)
        if response:
            return self.receive()

    def get_target_speed(self):
        inst = [0, 53, 42, 0, 0, 0]
        self.send(inst)
        return self.receive()

#    def set_running_current(self, denom, response=True):
#        if denom < 10:
#            print "Fractional current denominator too low; using 10"
#            denom = 10
#        if denom > 127:
#            print "Fractional current denominator too high; using 127"
#            denom = 127
#        inst = [0, 38]
#        inst.extend(four_byte_representation(denom))
#        self.send(inst)
#        if response:
#            return self.receive()
#
#    def get_running_current(self):
#        inst = [0, 53, 38, 0, 0, 0]
#        self.send(inst)
#        return self.receive()
#
#    def set_maximum_range(self, response=True):
#        self.send([0, 44, 72, 89, 4, 0])
#        ## This limit was determined empirically for the THz setup
#        if response:
#            return self.receive()
            
    def move_home(self, response=True):
        assert self.pending_moves == 0
        self.send([0, 1, 0, 0, 0, 0])
        self.pending_moves = len(self.devices)
        if response:
            return self.finish_moving()
        return None

#    def restore_settings(self, response=True):
#        self.send([0, 36, 0, 0, 0, 0])
#        if response:
#            return self.receive()
            
    def renumber_all_devices(self):
        self.serial.flushInput()
        self.serial.flushOutput()
        self.send([0, 2, 0, 0, 0, 0])
        time.sleep(.8)
        response = []
        while self.serial.inWaiting() > 0:
            response.append(self.receive())
        return response
    
    def close(self):
        self.serial.close()

def four_byte_representation(x):
    x = int(x)
    bignum = 4294967296 ##256**4
    if abs(x) >= (bignum)/2:
        print "x is too big to represent as a signed, four-byte integer"
    if x < 0:
        x += bignum
    byteList = [0, 0, 0, 0]
    for i in range(4):
        byteList[i] = int(x%256)
        x = x // 256
    return byteList

if __name__ == '__main__':
    try:
        my_stage = Stage(timeout=20)
        print my_stage.move(0, movetype='absolute', axis='all')
        print my_stage.move(50000, movetype='absolute', axis='all')
        print my_stage.move(0, movetype='absolute', axis='all')
    finally:
        my_stage.close()
