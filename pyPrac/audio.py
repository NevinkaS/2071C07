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
    ser.set_buffer_size(rx_size=1000000) # set buffer size to 1MB
    ser.reset_input_buffer() # remove stray data from buffer before recording
    # send instructions and data to stm
    ser.write(b'OO') 
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
    time.sleep(0.1)  
    ser.write(b'OO')
    print("Recording ended.")
    print(f"Received {int(len(samples)/1.5)} samples.")  # we receive 1.5 bytes per sample
    time.sleep(0.01) # wait a bit for stm to receive before closing
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
        ser.set_buffer_size(rx_size=1000000) # set buffer size to 1MB
        ser.reset_input_buffer()  # remove stray data from buffer before recording
        # send instructions and dat to stm
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
            ser.write(b'OO')
            time.sleep(0.01) # wait a bit for stm to receive before closing
            ser.close()
            print(f"Received {int(len(samples)/1.5)} samples.") # we receive 1.5 bytes per sample
            break

        # end the sending of samples and disconnect
        ser.write(b'OO')
        time.sleep(0.01) # wait a bit for stm to receive before closing
        ser.close()

        print(f"Received {int(len(samples)/1.5)} samples.") # we receive 1.5 bytes per sample
    
        # call outmodes() to select the output mode
        outmodes(samples)

# Output function
# =========================
def outmodes(raw_data):

    # unpack 3-byte chunks back into two 12-bit samples
    unpacked_data = []
    for i in range(0, len(raw_data) - 2, 3):
        b0 = raw_data[i]
        b1 = raw_data[i+1]
        b2 = raw_data[i+2]
        
        s1 = (b0 << 4) | (b1 >> 4) # 8 bits from byte 1, first 4 from byte 2
        s2 = ((b1 & 0x0F) << 8) | b2 # last 4 from byte 2, 8 from byte 3
        
        unpacked_data.append(s1)
        unpacked_data.append(s2)
        
    data = np.array(unpacked_data, dtype=np.float32) # so it isnt rounded to integer
    data = (data - data.min()) / (data.max() - data.min()) # normalisation
    data = data * 65535.0  # multiply up to 16 bit
    data = data - 32768.0 # wav 16 bit takes signed so shift by half
    data = np.clip(data, -32768, 32767) # removes any errored numbers that exceeded the bounds of 16 bit
    data = data.astype(np.int16) # convert back to int (16 bit signed)
    

    print("\nEnter Y/N for output types.")

    # .wav audio file
    if((input("Do you want wav output (Y/N): ")).lower() == 'y'):
        filename="test.wav"
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(1) # mono audio (single channel)
            wf.setsampwidth(2) # 16 bits (2 bytes) per sample
            wf.setframerate(SAMPLE_RATE) # set the sample rate that the data was recorded at
            wf.writeframes(data.tobytes()) # write the audio data to the file

    # .csv file raw audio data
    if((input("Do you want csv output (Y/N): ")).lower() == 'y'):
        with open("audio.csv", "w", newline="") as f: # open csv text file
            writer = csv.writer(f)
            writer.writerow(["Sample Rate", SAMPLE_RATE]) # write sample rate to the file in first line
            writer.writerow(["Sample Number", "Amplitude"]) # header for rest of data
            for i in range(len(data)): # write the sample number and its amplitude (integer value of the binary data)
                sample = data[i]
                writer.writerow([i, sample])

    # png (waveform)
    if((input("Do you want png output (Y/N): ")).lower() == 'y'):
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
                if seconds > 60 or seconds<1:
                    raise ValueError # limit time to 60 since 16 bit timers on stm only handle up to 65,500 milliseconds
                break
            except ValueError:
                print("Enter a number with 1 and 60")
        
    elif usr_selection=="D":
        while True:
            try:
                distance = int(input("Enter Distance: "))
                print(f"User Selected: {usr_selection} with {distance}cm")
                if distance<5 or distance>40:
                    raise ValueError() # if distance is less than 5 ultrasonic can be unreliable 
                break
            except ValueError:
                print("Enter a number within 5 and 40")

    input("Press Enter to Run")


    if usr_selection=="M":
        record_manual(seconds)
    elif usr_selection=="D":
        record_distance_trigger(distance=distance)


# main to run the program
while True:
    run()
