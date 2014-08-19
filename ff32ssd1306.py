#-----------------------------------------------------------------------------------------
# ff32ssd1306.py by Paul Merkx 11/7/14
# About:
# Library for driving OLED displays based on SSD1306 chip. 
# Uses FlyFish technology FF32 multi purpose interface chip (www.flyfish-tech.com)
# to convert [RaspberryPi]--USB-->[FF23]--I2C-->[SSD1306 based OLED display]
# Power of both display and FF32 are supplied through the USB port of the RaspberryPi
#
# Acknowledgements:
# Extension to the code on https://github.com/guyc/py-gaugette
# by Guy Carpenter, Clearwater Software (written for SPI)
# Took out the SPI communications and replaced them with I2C communications through FF32.
# Guy Carpenter's code is based heavily on Adafruit's Arduino library
# https://github.com/adafruit/Adafruit_SSD1306
# written by Limor Fried/Ladyada for Adafruit Industries.
#
# This library has been tested with with: 
# banggood.com 0.96 Inch I2C IIC Serial 128 x 64 OLED LCD LED Display Module For Arduino
# but could work with other SSD1306 based displays too with modifications (see below).
# 
# Wiring:
#  ____         ______             _________
# |    |       |      |A6------SDA|         |
# |Rpi |-USB---| FF32 |A5------SCL| OLED    |
# |    |       |      |GND-----GND| SSD1306 |
# |____|       |______|Vdd-----Vcc|_________|
#
# The datasheet for the SSD1306 is available
#   http://www.adafruit.com/datasheets/SSD1306.pdf
#
#
# About SSD1306 based displays:
# Many variants exist of these SSD1306 based displays. Their difference might require
# different wiring and/or code. Differences i have seen:
# 1. Fixed SPI or I2C wired.  This library only handles I2C based wired models (by now)
# 2. I2C address: 3C is default, but by soldering jumper this might be 3D also.
# 3. Separate SDAin and SDAout? 
#    If not check if the single SDA leads to both pin 19 and 20 on your board
#    If yes: tie SDAin and SDAout together. Otherwise there will be no ACK received
#       as the ACK will only appear on SDAout. Otherwise modify the FF32 code to ignore
#       the "No ack received" exception. Note that there will be no check if the correct 
#       i2c address is used by doing so.
# 4. Is Vcc separately supplied?
#    Vdd should be 3.3V Vcc should be 7..12V. If Vcc is not supplied separately (pin 28)
#    but grounded through a capacitor then the panel supply is generated through a charge pump
#    Vbat is used to generate this and might be externally supplied (5V) or tied to Vdd.
#
#----------------------------------------------------------------------------------------------

import pyff32
import font5x8
import time
import sys

class SSD1306:

    # Class constants are externally accessible as gaugette.ssd1306.SSD1306.CONST
    # or my_instance.CONST
    
    MAX_FF32_MSG          = 60      # Max nr of bytes allowed to send to FF32 (I2C address excluded) in one message
    
    COMMAND_MODE          = 0x00    # Continuation=0, Command/Data=0
    DATA_MODE             = 0x40    # Continuation=0, Command/Data=1
    
    EXTERNAL_VCC          = 0x1     # Vcc is supplied (7..12V) externally - check your specific board
    SWITCH_CAP_VCC        = 0x2     # Vcc is generated from Vbat by charge pump (Vbat might be connected to Vdd)
        
    SET_LOW_COLUMN        = 0x00
    SET_HIGH_COLUMN       = 0x10
    SET_MEMORY_MODE       = 0x20
    SET_COL_ADDRESS       = 0x21
    SET_PAGE_ADDRESS      = 0x22
    RIGHT_HORIZ_SCROLL    = 0x26
    LEFT_HORIZ_SCROLL     = 0x27
    VERT_AND_RIGHT_HORIZ_SCROLL = 0x29
    VERT_AND_LEFT_HORIZ_SCROLL  = 0x2A
    DEACTIVATE_SCROLL     = 0x2E
    ACTIVATE_SCROLL       = 0x2F
    SET_START_LINE        = 0x40
    SET_CONTRAST          = 0x81
    CHARGE_PUMP           = 0x8D
    SEG_REMAP             = 0xA0
    SET_VERT_SCROLL_AREA  = 0xA3
    DISPLAY_ALL_ON_RESUME = 0xA4
    DISPLAY_ALL_ON        = 0xA5
    NORMAL_DISPLAY        = 0xA6
    INVERT_DISPLAY        = 0xA7
    DISPLAY_OFF           = 0xAE
    DISPLAY_ON            = 0xAF
    COM_SCAN_INC          = 0xC0
    COM_SCAN_DEC          = 0xC8
    SET_DISPLAY_OFFSET    = 0xD3
    SET_COM_PINS          = 0xDA
    SET_VCOM_DETECT       = 0xDB
    SET_DISPLAY_CLOCK_DIV = 0xD5
    SET_PRECHARGE         = 0xD9
    SET_MULTIPLEX         = 0xA8

    MEMORY_MODE_HORIZ     = 0x00
    MEMORY_MODE_VERT      = 0x01
    MEMORY_MODE_PAGE      = 0x02


    def __init__(self, slave_addr=0x3C, scl_pin=("A",5), sda_pin=("A",6), buffer_rows=64, buffer_cols=128, rows=64, cols=128):
        self.cols = cols
        self.rows = rows
        self.buffer_rows = buffer_rows
        self.mem_bytes = self.buffer_rows * self.cols / 8 # total bytes in SSD1306 display ram
        self.scl_pin = scl_pin
        self.sda_pin = sda_pin
        self.slave_addr = slave_addr
        with pyff32.FF32() as ff32:
        # configure I2C bus on FF32 chip
            ff32.setI2CPins(self.scl_pin, self.sda_pin)
        self.font = font5x8.Font5x8
        self.col_offset = 0
        self.bitmap = self.Bitmap(buffer_cols, buffer_rows)
        self.flipped = False

    def command(self, *commandbytes):
        # Every command byte and following parameter(s) has to be preceded by
        # the COMMAND_MODE byte to mark it as command.
        # Command mode: first byte to send = COMMAND_MODE (Co=0 D/C#=1)
        for i in commandbytes:
            senddata = bytearray([self.COMMAND_MODE])
            senddata.append(i)
            with pyff32.FF32() as ff32:
                ff32.writeBlockI2C(self.slave_addr, senddata)
 
    def data(self, databytes):
        # Data mode: first byte to send = DATA_MODE (Co=0 D/C#=1)
        # Databytes follow after that. The datapointer is maintained by SSD1306
        # FF32 can only send 60byte chuncks of data at a time
        # So send chunk if senddata array reaches max chunk size
        senddata = bytearray([self.DATA_MODE])
        for i in range(0,len(databytes)):
            senddata.append(databytes[i])
            if len(senddata) >= self.MAX_FF32_MSG-1:
                with pyff32.FF32() as ff32:
                    ff32.writeBlockI2C(self.slave_addr, senddata)
                # re-init senddata for next chunk
                senddata = bytearray([self.DATA_MODE])
        # send remainder (at least if senddata contains more than DATA_MODE byte)
        if len(senddata) > 1:
                with pyff32.FF32() as ff32:
                    ff32.writeBlockI2C(self.slave_addr, senddata)
        
    def begin(self, vcc_state = SWITCH_CAP_VCC):
        time.sleep(0.001) # 1ms
        self.command(self.DISPLAY_OFF)
        self.command(self.SET_DISPLAY_CLOCK_DIV, 0x80)

        # support for 128x32 and 128x64 line models
        if self.rows == 64:
            self.command(self.SET_MULTIPLEX, 0x3F) 
            self.command(self.SET_COM_PINS, 0x12)
        else:
            self.command(self.SET_MULTIPLEX, 0x1F)
            self.command(self.SET_COM_PINS, 0x02)
            
        self.command(self.SET_DISPLAY_OFFSET, 0x00)
        self.command(self.SET_START_LINE | 0x00)
        # support for internally supplied Vcc (Charge pump) or 
        # external supplied Vcc
        if (vcc_state == self.EXTERNAL_VCC):
            self.command(self.CHARGE_PUMP, 0x10)
        else:
            self.command(self.CHARGE_PUMP, 0x14)
        self.command(self.SET_MEMORY_MODE, 0x00)
        self.command(self.SEG_REMAP | 0x01)
        self.command(self.COM_SCAN_DEC)
        self.command(self.SET_CONTRAST, 0xbf)
        if (vcc_state == self.EXTERNAL_VCC):
            self.command(self.SET_PRECHARGE, 0x22)
        else:
            self.command(self.SET_PRECHARGE, 0xF1)
        self.command(self.SET_VCOM_DETECT, 0x40)
        self.command(self.DISPLAY_ALL_ON_RESUME)
        self.command(self.NORMAL_DISPLAY)
        self.command(self.DISPLAY_ON)
    
    def select(self):
        # reconfigure I2C bus on FF32 chip after talking to other I2C device
        with pyff32.FF32() as ff32:
            ff32.setI2CPins(self.scl_pin, self.sda_pin)
   
    def clear_display(self):
        self.bitmap.clear()

    def invert_display(self):
        self.command(self.INVERT_DISPLAY)

    def flip_display(self, flipped=True):
        self.flipped = flipped
        if flipped:
            self.command(self.COM_SCAN_INC)
            self.command(self.SEG_REMAP | 0x00)
        else:
            self.command(self.COM_SCAN_DEC)
            self.command(self.SET_COM_PINS, 0x02)

    def normal_display(self):
        self.command(self.NORMAL_DISPLAY)

    def set_contrast(self, contrast=0x8f):
        self.command(self.SET_CONTRAST, contrast)

    def display(self):
        self.display_block(self.bitmap, 0, 0, self.cols, self.col_offset)

    def display_cols(self, start_col, count):
        self.display_block(self.bitmap, 0, start_col, count, self.col_offset)

    # Transfers data from the passed bitmap (instance of ssd1306.Bitmap)
    # starting at row <row> col <col>.
    # Both row and bitmap.rows will be divided by 8 to get page addresses,
    # so both must divide evenly by 8 to avoid surprises.
    #
    # bitmap:     instance of Bitmap
    #             The number of rows in the bitmap must be a multiple of 8.
    # row:        Starting row to write to - must be multiple of 8
    # col:        Starting col to write to.
    # col_count:  Number of cols to write.
    # col_offset: column offset in buffer to write from
    #  
    def display_block(self, bitmap, row, col, col_count, col_offset=0):
        page_count = bitmap.rows >> 3
        page_start = row >> 3
        page_end   = page_start + page_count - 1
        col_start  = col
        col_end    = col + col_count - 1
        self.command(self.SET_MEMORY_MODE, self.MEMORY_MODE_VERT)
        self.command(self.SET_PAGE_ADDRESS, page_start, page_end)
        self.command(self.SET_COL_ADDRESS, col_start, col_end)
        start = col_offset * page_count
        length = col_count * page_count
        self.data(bitmap.data[start:start+length])

    # Diagnostic print of the memory buffer to stdout 
    def dump_buffer(self):
        self.bitmap.dump()

    def draw_pixel(self, x, y, on=True):
        self.bitmap.draw_pixel(x,y,on)
        
    def draw_text(self, x, y, string):
        font_bytes = self.font.bytes
        font_rows = self.font.rows
        font_cols = self.font.cols
        for c in string:
            p = ord(c) * font_cols
            for col in range(0,font_cols):
                mask = font_bytes[p]
                p+=1
                for row in range(0,8):
                    self.draw_pixel(x,y+row,mask & 0x1)
                    mask >>= 1
                x += 1

    def draw_text2(self, x, y, string, size=2, space=1):
        font_bytes = self.font.bytes
        font_rows = self.font.rows
        font_cols = self.font.cols
        for c in string:
            p = ord(c) * font_cols
            for col in range(0,font_cols):
                mask = font_bytes[p]
                p+=1
                py = y
                for row in range(0,8):
                    for sy in range(0,size):
                        px = x
                        for sx in range(0,size):
                            self.draw_pixel(px,py,mask & 0x1)
                            px += 1
                        py += 1
                    mask >>= 1
                x += size
            x += space

    def clear_block(self, x0,y0,dx,dy):
        self.bitmap.clear_block(x0,y0,dx,dy)
        
    def draw_text3(self, x, y, string, font):
        return self.bitmap.draw_text(x,y,string,font)

    def text_width(self, string, font):
        return self.bitmap.text_width(string, font)

    class Bitmap:
    
        # Pixels are stored in column-major order!
        # This makes it easy to reference a vertical slice of the display buffer
        # and we use the to achieve reasonable performance vertical scrolling 
        # without hardware support.
        def __init__(self, cols, rows):
            self.rows = rows
            self.cols = cols
            self.bytes_per_col = rows / 8
            self.data = [0] * (self.cols * self.bytes_per_col)
    
        def clear(self):
            for i in range(0,len(self.data)):
                self.data[i] = 0

        # Diagnostic print of the memory buffer to stdout 
        def dump(self):
            for y in range(0, self.rows):
                mem_row = y/8
                bit_mask = 1 << (y % 8)
                line = ""
                for x in range(0, self.cols):
                    mem_col = x
                    offset = mem_row + self.rows/8 * mem_col
                    if self.data[offset] & bit_mask:
                        line += '*'
                    else:
                        line += ' '
                print('|'+line+'|')
        
  
        def draw_pixel(self, x, y, on=True):
            if (x<0 or x>=self.cols or y<0 or y>=self.rows):
                return
            mem_col = x
            mem_row = y / 8
            bit_mask = 1 << (y % 8)
            offset = mem_row + self.rows/8 * mem_col
    
            if on:
                self.data[offset] |= bit_mask
            else:
                self.data[offset] &= (0xFF - bit_mask)
    
        def clear_block(self, x0,y0,dx,dy):
            for x in range(x0,x0+dx):
                for y in range(y0,y0+dy):
                    self.draw_pixel(x,y,0)

        # returns the width in pixels of the string allowing for kerning & interchar-spaces
        def text_width(self, string, font):
            x = 0
            prev_char = None
            for c in string:
                if (c<font.start_char or c>font.end_char):
                    if prev_char != None:
                        x += font.space_width + prev_width + font.gap_width
                    prev_char = None
                else:
                    pos = ord(c) - ord(font.start_char)
                    (width,offset) = font.descriptors[pos]
                    if prev_char != None:
                        x += font.kerning[prev_char][pos] + font.gap_width
                    prev_char = pos
                    prev_width = width
                    
            if prev_char != None:
                x += prev_width
                
            return x
              
        def draw_text(self, x, y, string, font):
            height = font.char_height
            prev_char = None
    
            for c in string:
                if (c<font.start_char or c>font.end_char):
                    if prev_char != None:
                        x += font.space_width + prev_width + font.gap_width
                    prev_char = None
                else:
                    pos = ord(c) - ord(font.start_char)
                    (width,offset) = font.descriptors[pos]
                    if prev_char != None:
                        x += font.kerning[prev_char][pos] + font.gap_width
                    prev_char = pos
                    prev_width = width
                    
                    bytes_per_row = (width + 7) / 8
                    for row in range(0,height):
                        py = y + row
                        mask = 0x80
                        p = offset
                        for col in range(0,width):
                            px = x + col
                            if (font.bitmaps[p] & mask):
                                self.draw_pixel(px,py,1)  # for kerning, never draw black
                            mask >>= 1
                            if mask == 0:
                                mask = 0x80
                                p+=1
                        offset += bytes_per_row
              
            if prev_char != None:
                x += prev_width
    
            return x

    # This is a helper class to display a scrollable list of text lines.
    # The list must have at least 1 item.
    class ScrollingList:
        def __init__(self, ssd1306, list, font):
            self.ssd1306 = ssd1306
            self.list = list
            self.font = font
            self.position = 0 # row index into list, 0 to len(list) * self.rows - 1
            self.offset = 0   # led hardware scroll offset
            self.pan_row = -1
            self.pan_offset = 0
            self.pan_direction = 1
            self.bitmaps = []
            self.rows = ssd1306.rows
            self.cols = ssd1306.cols
            self.bufrows = self.rows * 2
            downset = (self.rows - font.char_height)/2
            for text in list:
                width = ssd1306.cols
                text_bitmap = ssd1306.Bitmap(width, self.rows)
                width = text_bitmap.draw_text(0,downset,text,font)
                if width > 128:
                    text_bitmap = ssd1306.Bitmap(width+15, self.rows)
                    text_bitmap.draw_text(0,downset,text,font)
                self.bitmaps.append(text_bitmap)
                
            # display the first word in the first position
            self.ssd1306.display_block(self.bitmaps[0], 0, 0, self.cols)
    
        # how many steps to the nearest home position
        def align_offset(self):
            pos = self.position % self.rows
            midway = (self.rows/2)
            delta = (pos + midway) % self.rows - midway
            return -delta

        def align(self, delay=0.005):
            delta = self.align_offset()
            if delta!=0:
                steps = abs(delta)
                sign = delta/steps
                for i in range(0,steps):
                    if i>0 and delay>0:
                        time.sleep(delay)
                    self.scroll(sign)
            return self.position / self.rows
    
        # scroll up or down.  Does multiple one-pixel scrolls if delta is not >1 or <-1
        def scroll(self, delta):
            if delta == 0:
                return
    
            count = len(self.list)
            step = cmp(delta, 0)
            for i in range(0,delta, step):
                if (self.position % self.rows) == 0:
                    n = self.position / self.rows
                    # at even boundary, need to update hidden row
                    m = (n + step + count) % count
                    row = (self.offset + self.rows) % self.bufrows
                    self.ssd1306.display_block(self.bitmaps[m], row, 0, self.cols)
                    if m == self.pan_row:
                        self.pan_offset = 0
                self.offset = (self.offset + self.bufrows + step) % self.bufrows
                self.ssd1306.command(self.ssd1306.SET_START_LINE | self.offset)
                max_position = count * self.rows
                self.position = (self.position + max_position + step) % max_position
    
        # pans the current row back and forth repeatedly.
        # Note that this currently only works if we are at a home position.
        def auto_pan(self):
            n = self.position / self.rows
            if n != self.pan_row:
                self.pan_row = n
                self.pan_offset = 0
                
            text_bitmap = self.bitmaps[n]
            if text_bitmap.cols > self.cols:
                row = self.offset # this only works if we are at a home position
                if self.pan_direction > 0:
                    if self.pan_offset <= (text_bitmap.cols - self.cols):
                        self.pan_offset += 1
                    else:
                        self.pan_direction = -1
                else:
                    if self.pan_offset > 0:
                        self.pan_offset -= 1
                    else:
                        self.pan_direction = 1
                self.ssd1306.display_block(text_bitmap, row, 0, self.cols, self.pan_offset)
    