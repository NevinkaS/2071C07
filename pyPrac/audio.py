import numpy as np
import wave
import serial
import serial.tools.list_ports
import matplotlib.pyplot as plt
import csv
import time

# # poll serial devices
# devices = serial.tools.list_ports.comports()
# for device in devices:
#     print(device)

# Magic Values
SERIAL_PORT = "COM10"
BAUD_RATE = 921600
SAMPLE_RATE = 48048 # 32,000,000/(6*111) prescaler 5 period 110

# Recording functions
# =========================
def record_manual(duration_seconds):
    # get the number of samples required for x seconds
    num_samples = SAMPLE_RATE * duration_seconds

    # connect to STM and start sending samples in the selected mode's method
    print(f"\nOpening {SERIAL_PORT} at {BAUD_RATE} baud...")
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
    ser.reset_input_buffer()
    ser.write('O'.encode())
    ser.write('O'.encode())
    ser.write('M'.encode())
    ser.write(duration_seconds.to_bytes(1, byteorder='little'))


    # record the sent samples
    print("Recording started...")
    samples = []
    while len(samples) < num_samples*1.5: # every sample is 1.5 bytes
        bytes = ser.read(size=3600)
        if bytes:
            samples.extend(bytes)

    # since samples are gotten in chunks of 1800, then cut down to required amount
    samples = samples[:int(num_samples*1.5)]
    # end the sending of samples and disconnect
    ser.write('O'.encode())
    ser.write('O'.encode())
    ser.flush()          # Force Python to push the bytes out of the PC buffer
    time.sleep(0.1)
    print("Recording ended.")
    print(f"Received {int(len(samples)/1.5)} samples.")
    time.sleep(0.01)
    ser.close()

    # call outmodes() to select the output mode
    outmodes(samples)


def record_distance_trigger(distance):
    """
    This assumes the Processing STM only sends data to the PC when
    the ultrasonic sensor has triggered recording.
    """
    # This needs to keep running while user doesnt leave this mode
    while(True):

        # connect to STM and start sending samples in the selected mode's method
        print(f"\nOpening {SERIAL_PORT} at {BAUD_RATE} baud...")
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
        ser.reset_input_buffer()
        ser.write('D'.encode())
        ser.write(distance.to_bytes(1, byteorder='little'))

        samples = []
        print("Distance Trigger Mode started.")
        print("Waiting for STM to send triggered audio...")
        print("Press Ctrl+C to stop.\n")

        try:
            # wait until the first chunk arrives
            while True:
                bytes = ser.read(size=1800)
                if bytes:
                    samples.extend(bytes)
                    print("Trigger detected. Recording...")
                    break

            # read incoming audio samples, saving the amount of empty reads (timeouts)
            empty_reads = 0
            while True:
                data = ser.read(size=1800)
                if data:
                    samples.extend(data)
                    empty_reads = 0
                else:
                    empty_reads += 1

                # If no data arrives for a short time, assume STM stopped recording
                # 3 is chosen for safety in case of a dropout
                if empty_reads >= 3:
                    print("Trigger recording ended.")
                    break

        # if user decides to change the mode by Ctrl+C then stop recording straight away and only process currently save data 
        # (bytes in transmission are forgotten about)
        except KeyboardInterrupt:
            print("Stopped by user.")
            # end the sending of samples and disconnect
            ser.write('O'.encode())
            ser.write('O'.encode())
            ser.write('O'.encode())
            ser.write('O'.encode())
            ser.close()
            print(f"Received {int(len(samples)/1.5)} samples.")
            break

        # end the sending of samples and disconnect
        ser.write('O'.encode())
        ser.write('O'.encode())
        ser.write('O'.encode())
        ser.write('O'.encode())
        ser.close()

        print(f"Received {int(len(samples)/1.5)} samples.")
    
        # call outmodes() to select the output mode
        outmodes(samples)

# Output function
# =========================
def outmodes(raw_data):
    # user selection for mode
    mode = " "
    while(mode not in {"wav","png", "csv"}):
        mode = input("Enter the mode you want the data in (wav, png, csv): ")

    # 1. Unpack 3-byte chunks back into two 12-bit samples
    unpacked_data = []
    for i in range(0, len(raw_data) - 2, 3):
        b0 = raw_data[i]
        b1 = raw_data[i+1]
        b2 = raw_data[i+2]
        
        s1 = (b0 << 4) | (b1 >> 4)
        s2 = ((b1 & 0x0F) << 8) | b2
        
        unpacked_data.append(s1)
        unpacked_data.append(s2)
        
    data = np.array(unpacked_data, dtype=np.float32) # so it isnt rounded to integer
    # 2. Map 12-bit ADC range (0 to 4095) to 16-bit WAV range (-32768 to 32767)
    # data = (data - data.min()) / (data.max() - data.min())
    data = (data / 4095.0) # divide down to 0-1
    data = data * 65535.0  # multiply up to 16 bit
    data = data - 32768.0 # wav 16 bit takes signed so shift by half
    data = np.clip(data, -32768, 32767) # removes any errored numbers that exceeded the bounds of 16 bit
    data = data.astype(np.int16) # convert back to int (16 bit signed)
    
    # # convert list to numpy array
    # data = np.array(raw_data)
    # # normalise to 0 to 255 range:
    # # data = (data - data.min()) / data.max()
    # data = (data - data.min()) / (data.max() - data.min())
    # data = data * 255 # scale to 0-255
    # data = data.astype(np.uint8) # convert to uint8 type

    # .wav audio file
    if(mode=="wav"):
        filename="test.wav"
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(1) # mono audio (single channel)
            wf.setsampwidth(2) # 16 bits (2 bytes) per sample
            wf.setframerate(SAMPLE_RATE) # set the sample rate that the data was recorded at
            wf.writeframes(data.tobytes()) # write the audio data to the file

    # .csv file raw audio data
    if(mode=="csv"):
        with open("audio.csv", "w", newline="") as f: # open csv text file
            writer = csv.writer(f)
            writer.writerow(["Sample Rate", SAMPLE_RATE]) # write sample rate to the file in first line
            writer.writerow(["Sample Number", "Amplitude"]) # header for rest of data
            for i in range(len(data)): # write the sample number and its amplitude (integer value of the binary data)
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

# =========================
# Run the program, getting user input and chosing recording function appropriately
def run():
    # get user selection of recording mode
    # keep promptin untill correct choice entered
    print("Chose:\nManual Recording Mode (M)\nDistance Trigger Mode (D)")
    usr_selection = ""
    while(True):
        usr_selection = input("Enter Recording Mode: ").upper()
        if usr_selection=="M" or usr_selection=="D" :
            break

    # get the number of seconds or distance the user wants
    # keep prompting until acceptable number entered
    seconds = 0
    distance = 0
    if usr_selection=="M":
        while True:
            try:
                seconds = int(input("Enter number of seconds: "))
                print(f"User Selected: {usr_selection} with {seconds}s")
                break
            except ValueError:
                print("Enter a number")
        
    elif usr_selection=="D":
        while True:
            try:
                distance = int(input("Enter Distance: "))
                print(f"User Selected: {usr_selection} with {distance}cm")
                if distance<5:
                    raise ValueError()
                break
            except ValueError:
                print("Enter a number")

    input("Press Enter to Run")


    if usr_selection=="M":
        record_manual(seconds)
    elif usr_selection=="D":
        record_distance_trigger(distance=distance)


# main to run the program
while True:
    run()
