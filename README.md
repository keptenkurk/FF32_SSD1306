FF32_SSD1306
============

Python code driving SSD1306 based OLED display through Flyfish-tech.com FF32 USB interface chip

Library for driving OLED displays based on SSD1306 chip. 
Uses FlyFish technology FF32 multi purpose interface chip (www.flyfish-tech.com)
to convert [RaspberryPi]--USB-->[FF23]--I2C-->[SSD1306 based OLED display]
Power of both display and FF32 are supplied through the USB port of the RaspberryPi

Acknowledgements:
Extension to the code on https://github.com/guyc/py-gaugette
by Guy Carpenter, Clearwater Software (written for SPI)
Took out the SPI communications and replaced them with I2C communications through FF32.
Guy Carpenter's code is based heavily on Adafruit's Arduino library
https://github.com/adafruit/Adafruit_SSD1306
written by Limor Fried/Ladyada for Adafruit Industries.

This library has been tested with with: 
banggood.com 0.96 Inch I2C IIC Serial 128 x 64 OLED LCD LED Display Module For Arduino
but could work with other SSD1306 based displays too with modifications (see below).
 
The datasheet for the SSD1306 is available
   http://www.adafruit.com/datasheets/SSD1306.pdf


About SSD1306 based displays:
Many variants exist of these SSD1306 based displays. Their difference might require
different wiring and/or code. Differences i have seen:
1. Fixed SPI or I2C wired.  This library only handles I2C based wired models (by now)
2. I2C address: 3C is default, but by soldering jumper this might be 3D also.
3. Separate SDAin and SDAout? 
  If not check if the single SDA leads to both pin 19 and 20 on your board
  If yes: tie SDAin and SDAout together. Otherwise there will be no ACK received
     as the ACK will only appear on SDAout. Otherwise modify the FF32 code to ignore
     the "No ack received" exception. Note that there will be no check if the correct 
     i2c address is used by doing so.
4. Is Vcc separately supplied?
  Vdd should be 3.3V Vcc should be 7..12V. If Vcc is not supplied separately (pin 28)
  but grounded through a capacitor then the panel supply is generated through a charge pump
  Vbat is used to generate this and might be externally supplied (5V) or tied to Vdd.

