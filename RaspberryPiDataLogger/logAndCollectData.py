#!/usr/bin/env python3

import time
import colorsys
import sys
import os
import csv 
import ST7735
import numpy
import sounddevice
try:
    # Transitional fix for breaking change in LTR559
    from ltr559 import LTR559
    ltr559 = LTR559()
except ImportError:
    import ltr559

from bme280 import BME280
from pms5003 import PMS5003, ReadTimeoutError as pmsReadTimeoutError, SerialTimeoutError
from enviroplus import gas
from subprocess import PIPE, Popen
from pathlib import Path
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from fonts.ttf import RobotoMedium as UserFont
import logging

logging.basicConfig(
    format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

logging.info("""logAndCollect.py - Displays readings from all of Enviro plus' sensors and saves them to a .csv fi

Press Ctrl+C to exit!

""")


# BME280 temperature/pressure/humidity sensor
bme280 = BME280()

# PMS5003 particulate sensor
pms5003 = PMS5003()
time.sleep(1.0)

# Create ST7735 LCD display class
st7735 = ST7735.ST7735(
    port=0,
    cs=1,
    dc=9,
    backlight=12,
    rotation=270,
    spi_speed_hz=10000000
)

# Initialize display
st7735.begin()

WIDTH = st7735.width
HEIGHT = st7735.height

# Set up canvas and font
img = Image.new('RGB', (WIDTH, HEIGHT), color=(0, 0, 0))
draw = ImageDraw.Draw(img)
font_size_small = 10
font_size_large = 20
font = ImageFont.truetype(UserFont, font_size_large)
smallfont = ImageFont.truetype(UserFont, font_size_small)
x_offset = 2
y_offset = 2

message = ""

# The position of the top bar
top_pos = 25

# Create a values dict to store the data
variables = ["temperature",
             "pressure",
             "humidity",
             "light",
             "oxidised",
             "reduced",
             "nh3",
             "pm1",
             "pm25",
             "pm10",
             "timestamp",
             "mic_amp_low",
             "mic_amp_mid",
             "mic_amp_high",
             "mic_amp_total"
             ]

units = ["C",
         "hPa",
         "%",
         "Lux",
         "kO",
         "kO",
         "kO",
         "ug/m3",
         "ug/m3",
         "ug/m3",
         "time",
         "%",
         "%",
         "%",
         "%"
         ]

duration = 4
sample_rate = 16000

# Define your own warning limits
# The limits definition follows the order of the variables array
# Example limits explanation for temperature:
# [4,18,28,35] means
# [-273.15 .. 4] -> Dangerously Low
# (4 .. 18]      -> Low
# (18 .. 28]     -> Normal
# (28 .. 35]     -> High
# (35 .. MAX]    -> Dangerously High
# DISCLAIMER: The limits provided here are just examples and come
# with NO WARRANTY. The authors of this example code claim
# NO RESPONSIBILITY if reliance on the following values or this
# code in general leads to ANY DAMAGES or DEATH.
limits = [[4, 18, 28, 35],
          [250, 650, 1013.25, 1015],
          [20, 30, 60, 70],
          [-1, -1, 30000, 100000],
          [-1, -1, 40, 50],
          [-1, -1, 450, 550],
          [-1, -1, 200, 300],
          [-1, -1, 50, 100],
          [-1, -1, 50, 100],
          [-1, -1, 50, 100],
          [0,0,0,0],
          [0,0,0,0],
          [0,0,0,0],
          [0,0,0,0],
          [0,0,0,0]]

# RGB palette for values on the combined screen
palette = [(0, 0, 255),           # Dangerously Low
           (0, 255, 255),         # Low
           (0, 255, 0),           # Normal
           (255, 255, 0),         # High
           (255, 0, 0)]           # Dangerously High

values = {}

#get time to create file name
t = time.localtime()
current_time = time.strftime("%Y:%m:%d:%H:%M:%S", t)
try:
    os.mkdir("./data")
except:
    print("error creating /data folder, it probably exists already")
filename = "./data/enviroData_" + current_time + ".csv"

logging.info("opening csv file" + filename)

file = open(filename, 'w')
writer = csv.writer(file)
writer.writerow(variables)
file.close()


def get_noise_profile(recording,
                      noise_floor=100,
                      low=0.12,
                      mid=0.36,
                      high=None):
    """Returns a noise charateristic profile.

    Bins all frequencies into 3 weighted groups expressed as a percentage of the total frequency range.

    :param noise_floor: "High-pass" frequency, exclude frequencies below this value
    :param low: Percentage of frequency ranges to count in the low bin (as a float, 0.5 = 50%)
    :param mid: Percentage of frequency ranges to count in the mid bin (as a float, 0.5 = 50%)
    :param high: Optional percentage for high bin, effectively creates a "Low-pass" if total percentage is less than 100%

    """

    if high is None:
        high = 1.0 - low - mid

    
    magnitude = numpy.abs(numpy.fft.rfft(recording[:, 0], n=sample_rate))

    sample_count = (sample_rate // 2) - noise_floor

    mid_start = noise_floor + int(sample_count * low)
    high_start = mid_start + int(sample_count * mid)
    noise_ceiling = high_start + int(sample_count * high)

    amp_low = numpy.mean(magnitude[noise_floor:mid_start])
    amp_mid = numpy.mean(magnitude[mid_start:high_start])
    amp_high = numpy.mean(magnitude[high_start:noise_ceiling])
    amp_total = (amp_low + amp_mid + amp_high) / 3.0

    return amp_low, amp_mid, amp_high, amp_total



# Displays data and text on the 0.96" LCD
def display_text(variable, data, unit):
    # Maintain length of list
    values[variable] = values[variable][1:] + [data]
    # Scale the values for the variable between 0 and 1
    vmin = min(values[variable])
    vmax = max(values[variable])
    colours = [(v - vmin + 1) / (vmax - vmin + 1) for v in values[variable]]
    # Format the variable name and value
    message = "{}: {:.1f} {}".format(variable[:4], data, unit)
    logging.info(message)
    draw.rectangle((0, 0, WIDTH, HEIGHT), (255, 255, 255))
    for i in range(len(colours)):
        # Convert the values to colours from red to blue
        colour = (1.0 - colours[i]) * 0.6
        r, g, b = [int(x * 255.0) for x in colorsys.hsv_to_rgb(colour, 1.0, 1.0)]
        # Draw a 1-pixel wide rectangle of colour
        draw.rectangle((i, top_pos, i + 1, HEIGHT), (r, g, b))
        # Draw a line graph in black
        line_y = HEIGHT - (top_pos + (colours[i] * (HEIGHT - top_pos))) + top_pos
        draw.rectangle((i, line_y, i + 1, line_y + 1), (0, 0, 0))
    # Write the text at the top in black
    draw.text((0, 0), message, font=font, fill=(0, 0, 0))
    st7735.display(img)


# Saves the data to be used in the graphs later and prints to the log
def save_data(idx, data):
    variable = variables[idx]
    # Maintain length of list
    values[variable] = values[variable][1:] + [data]
    unit = units[idx]
    message = "{}: {:.1f} {}".format(variable[:4], data, unit)
    #logging.info(message)


# Displays all the text on the 0.96" LCD
def display_everything():
    draw.rectangle((0, 0, WIDTH, HEIGHT), (0, 0, 0))
    column_count = 2
    row_count = (len(variables) / column_count)
    for i in range(len(variables)):
        variable = variables[i]
        data_value = values[variable][-1]
        unit = units[i]
        x = x_offset + ((WIDTH // column_count) * (i // row_count))
        y = y_offset + ((HEIGHT / row_count) * (i % row_count))
        message = "{}: {:.1f} {}".format(variable[:4], data_value, unit)
        lim = limits[i]
        rgb = palette[0]
        for j in range(len(lim)):
            if data_value > lim[j]:
                rgb = palette[j + 1]
        draw.text((x, y), message, font=smallfont, fill=rgb)
    st7735.display(img)

def clear_screen():
    st7735.set_backlight(0)
    #draw.rectangle((0, 0, WIDTH, HEIGHT), (0, 0, 0))
    #st7735.display(img)

# Displays all the text on the 0.96" LCD
def display_info(message, message1=""):
    
    print("Displaying info!", message)
    draw.rectangle((0, 0, WIDTH, HEIGHT), (0, 0, 255))

    draw.text((10,10), message, font=smallfont, fill=(0,0,255))
    draw.text((10,40), message1, font=smallfont, fill=(255,255,255))
    st7735.display(img)


# Get the temperature of the CPU for compensation
def get_cpu_temperature():
    process = Popen(['vcgencmd', 'measure_temp'], stdout=PIPE, universal_newlines=True)
    output, _error = process.communicate()
    return float(output[output.index('=') + 1:output.rindex("'")])

def get_millis():
    return round(time.time()*1000)

def main():
    # Tuning factor for compensation. Decrease this number to adjust the
    # temperature down, and increase to adjust up
    factor = 2.25

    cpu_temps = [get_cpu_temperature()] * 5

    delay = 0.1  # Debounce the proximity tap
    mode = 10    # The starting mode
    last_page = 0

    for v in variables:
        values[v] = [1] * WIDTH

    # The main loop
    try:
        while True:
            proximity = ltr559.get_proximity()
            # Everything on one screen
            cpu_temp = get_cpu_temperature()
            # Smooth out with some averaging to decrease jitter
            cpu_temps = cpu_temps[1:] + [cpu_temp]
            avg_cpu_temp = sum(cpu_temps) / float(len(cpu_temps))
            raw_temp = bme280.get_temperature()
            raw_data = raw_temp - ((avg_cpu_temp - raw_temp) / factor)
            save_data(0, raw_data)
            #display_everything()
            raw_data = bme280.get_pressure()
            save_data(1, raw_data)
            #display_everything()
            raw_data = bme280.get_humidity()
            save_data(2, raw_data)
            if proximity < 10:
                raw_data = ltr559.get_lux()
            else:
                raw_data = 1
            save_data(3, raw_data)
            #display_everything()
            gas_data = gas.read_all()
            save_data(4, gas_data.oxidising / 1000)
            save_data(5, gas_data.reducing / 1000)
            save_data(6, gas_data.nh3 / 1000)
          
            pms_data = None
            
            
            display_info("Recording audio...")
            
            
            print("Recording for", duration, " seconds with sample rate", sample_rate)
            recording = sounddevice.rec(
                int(duration * 16000),
                samplerate = 16000,
                blocking=True,
                channels=1,
                dtype='float64'
            )
            #print(recording)
            
            noise_profile = get_noise_profile(recording)
            save_data(10,noise_profile[0])
            save_data(11,noise_profile[1])
            save_data(12,noise_profile[2])
            save_data(13,noise_profile[3])
            print(noise_profile)
            
            display_info("Finished recording and analysing audio.")
            time.sleep(0.5)
            #how to log this now
            #get the time 
            t = time.localtime()
            current_time = time.strftime("%Y:%m:%d:%H:%M:%S", t)
            save_data(10,get_millis())
            print(current_time)
            
            valuesToSave = []
            for i in range(len(variables)):
                variable = variables[i]
                data_value = values[variable][-1]
                unit = units[i]
                valuesToSave.append(data_value)
                print(variable, ":", data_value, unit)
            
            valuesToSave+= [current_time]
            print("vals to save ", valuesToSave)
            st7735.set_backlight(5)
            display_info("Opening file...")
            file = open(filename, 'a')
            writer = csv.writer(file)
            writer.writerow(valuesToSave)
            file.close()
            print("wrote in .csv file")
            dir_path = os.path.dirname(os.path.realpath(__file__))
            display_info("current Folder is :", dir_path)
            time.sleep(2);
            display_info("Saved to file: ", filename) 
            time.sleep(2)
        
            display_everything()
     
            time.sleep(2)
            clear_screen()
            time.sleep(22) #+ 6 seconds waiting makes 30

    # Exit cleanly
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()

