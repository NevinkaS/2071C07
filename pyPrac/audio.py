import numpy as np
import wave
import serial
import serial.tools.list_ports
import numpy as np
import wave
import serial
import serial.tools.list_ports
import matplotlib.pyplot as plt
import csv

# poll serial devices
devices = serial.tools.list_ports.comports()

for device in devices:
    print(device)

SERIAL_PORT = "COM10"
BAUD_RATE = 921600
SAMPLE_RATE = 8333
raw_data = []

# Recording functions
# =========================
def record_manual(duration_seconds):
    num_samples = SAMPLE_RATE * duration_seconds

    print(f"\nOpening {SERIAL_PORT} at {BAUD_RATE} baud...")
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
    ser.write('M'.encode())
    ser.write(duration_seconds.to_bytes(1, byteorder='little'))

    samples = []

    print("Recording started...")
    i=0
    while i < num_samples:
        byte = ser.read(size=1)
        if byte:
            samples.append(byte[0])
        i+=1

    ser.write('O'.encode())
    ser.write('O'.encode())
    print("Recording ended.")
    print(f"Received {len(samples)} samples.")
    ser.close()

    outmodes(np.array(samples, dtype=np.uint8))


def record_distance_trigger(distance):
    """
    This assumes the Processing STM only sends data to the PC when
    the ultrasonic sensor has triggered recording.
    """
    while(True):
        print(f"\nOpening {SERIAL_PORT} at {BAUD_RATE} baud...")
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        ser.write('D'.encode())
        ser.write(distance.to_bytes(1, byteorder='little'))

        samples = []

        print("Distance Trigger Mode started.")
        print("Waiting for STM to send triggered audio...")
        print("Press Ctrl+C to stop.\n")

        try:
            # Wait until the first byte arrives
            while True:
                byte = ser.read(size=1)

                if byte:
                    samples.append(byte[0])
                    print("Trigger detected. Recording...")
                    break

            empty_reads = 0

            while True:
                data = ser.read(size=256)

                if data:
                    samples.extend(data)
                    empty_reads = 0
                else:
                    empty_reads += 1

                # If no data arrives for a short time, assume STM stopped recording
                if empty_reads >= 3:
                    print("Trigger recording ended.")
                    break

        except KeyboardInterrupt:
            print("Stopped by user.")
            ser.write('O'.encode())
            ser.write('O'.encode())
            ser.close()
            print(f"Received {len(samples)} samples.")
            break

        ser.write('O'.encode())
        ser.write('O'.encode())
        ser.close()

        print(f"Received {len(samples)} samples.")

        outmodes(np.array(samples, dtype=np.uint8))

# output function
# =============
def outmodes(raw_data):
    mode = " "
    while(mode not in {"wav","png", "csv"}):
        mode = input("Enter the mode you want the data in (): ")
    
    # convert list to numpy array
    data = np.array(raw_data)
    # normalise to 0 to 255 range:
    data = (data - data.min()) / data.max() # scale to 0-1
    data = data * 255 # scale to 0-255
    data = data.astype(np.uint8) # convert to uint8 type

    # .wav audio file
    if(mode=="wav"):
        filename="test.wav"
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(1) # mono audio (single channel)
            wf.setsampwidth(1) # 8 bits (1 byte ) per sample
            wf.setframerate(SAMPLE_RATE) # set the sample rate that the data was recorded at
            wf.writeframes(data.tobytes()) # write the audio data to the file

    # .csv file raw audio data
    if(mode=="csv"):
        with open("audio.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Sample Rate", SAMPLE_RATE])
            writer.writerow(["Sample Number", "Amplitude"])

            for i in range(len(data)):
                sample = data[i]
                writer.writerow([i, sample])

    # png (waveform)
    if(mode=="png"):
        time = np.arange(len(data)) / SAMPLE_RATE
        # plot
        plt.figure()
        plt.plot(time, data)
        plt.title("Audio Waveform")
        plt.xlabel("Time (seconds)")
        plt.ylabel("Amplitude")
        plt.grid(True)
        plt.savefig("waveform.png")
        plt.close()

    print("Outputted Selected File")


# Get Recording Mode
# =========================
print("Chose:\nManual Recording Mode (M)\nDistance Trigger Mode (D)")
usr_selection = ""
while(True):
    usr_selection = input("Enter Recording Mode: ").upper()
    if usr_selection=="M" or usr_selection=="D" :
        break

seconds = 0
distance = 0
if usr_selection=="M":
    seconds = int(input("Enter number of seconds: "))
    print(f"User Selected: {usr_selection} with {seconds}s")
elif usr_selection=="D":
    distance = int(input("Enter Distance: "))
    print(f"User Selected: {usr_selection} with {distance}cm")

input("run?")


if usr_selection=="M":
    record_manual(seconds)
elif usr_selection=="D":
    record_distance_trigger(distance=distance)

