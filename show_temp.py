#--------------------------------------------------------------------------
# show_temp.py
# Demonstration program which shows the current temperature from a DS18B20
# on a tiny SSD1306 oled
# v 1.0 Paul Merkx 19/8/14
#--------------------------------------------------------------------------

import ff32ssd1306
import ff32ds18b20
import time
import sys
import arial_16
import arial_24

fonts = []
fonts += [arial_16,
          arial_24]

print("init")
# define oled display and sensor objects
oled = ff32ssd1306.SSD1306(scl_pin=("A",5),sda_pin=("A",6))
sensor = ff32ds18b20.DS18B20(("B", 2))
print("begin")
# send initialization commands to oled
oled.begin()
print("clear")
# clear the oled
oled.clear_display()
oled.display()
oled.invert_display()
time.sleep(0.5)
oled.normal_display()
time.sleep(0.5)

while True:
    # retrieve current date and time
    text = time.strftime("%d%b %H:%M")
    # wipe area and show date/time
    oled.clear_block(0,0,128,16)
    textSize = oled.draw_text3(0,0,text,arial_16)
    # retrieve sensor temperature
    temperature=sensor.Read_Temp()
    temperaturestr = "{:.1f}".format(temperature)
    # wipe area and show temperature
    oled.clear_block(0,40,128,60)
    textSize=oled.draw_text3(0,40,temperaturestr+" "+chr(127)+"C",arial_24)
    # show all to the oled
    oled.display()
    time.sleep(1)



