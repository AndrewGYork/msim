import serial

class Z:
    def __init__(self):
        self.ser = serial.Serial(0, 9600)

    def move(self, zPos=0.00):
        print "Moving piezo stage to %0.2f"%(zPos)
        self.ser.write("move z=%0.2f\r"%(zPos))      # write a string

    def close(self):
        self.move(0)
        self.ser.close()             # close port

if __name__ == '__main__':
    import time
    piezo = Z()
    piezo.move(zPos=0.00)
    time.sleep(1)
    piezo.move(zPos=1.00)
    time.sleep(1)
    piezo.close()
