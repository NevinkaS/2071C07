import serial
import serial.tools.list_ports

# poll serial devices
devices = serial.tools.list_ports.comports()

# for device in devices:
#     print(device)

ser = serial.Serial("COM9", 115200)
repeat = True
while(repeat):
    # dat = input("enter: ") + '\n'
    # ser.write(dat.encode())

    # data = (ser.readline()).decode(errors="ignore")
    data = ser.read(size=1)

    print(data)

