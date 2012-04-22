import serial

def open_piezo():
    return serial.Serial(0, 9600)

def move(ser, zPos=0.00):
    print "Moving piezo stage to %0.2f"%(zPos)
    ser.write("move z=%0.2f\r"%(zPos))      # write a string

def close_piezo(ser):
    move(ser, 0)
    ser.close()             # close port

if __name__ == '__main__':
    import time
    ser = open_piezo()
    move(ser, zPos=0.00)
    time.sleep(1)
    move(ser, zPos=1.00)
    time.sleep(1)
    move(ser, zPos=0.00)
    close_piezo(ser)
