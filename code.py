# SPDX-FileCopyrightText: 2021 nitz — chris marc dailey https://cmd.wtf
# SPDX-License-Identifier: 0BSD

"""
Useful links:
https://circuitpython.readthedocs.io/projects/hid/en/latest/index.html
https://learn.adafruit.com/circuitpython-essentials/circuitpython-hid-keyboard-and-mouse
https://learn.adafruit.com/customizing-usb-devices-in-circuitpython?view=all
https://learn.adafruit.com/circuitpython-essentials/circuitpython-uart-serial
"""

from adafruit_hid.keycode import Keycode

# -----BEGIN CONFIG-----

# Config information:
# Each button on the main device sets a mode,
# From 0 to 3, left to right:
#   Red: Mode 0 (default)
#   Blue: Mode 1
#   Yellow: Mode 2
#   Green: Mode 3
#
# Each mode has a pair of keycodes. Those keycodes
# Will be sent as 'press' and 'release' when the
# left and right jack switches are pressed
# and released, respectively.
#
#

keymap = (
    (Keycode.F17, Keycode.F18), # Red, Mode 0 (default)
    (Keycode.F19, Keycode.F20), # Blue, Mode 1
    (Keycode.F21, Keycode.F22), # Yellow, Mode 2
    (Keycode.F23, Keycode.F24), # Green, Mode 3
)

# -----END CONFIG-----

import board
import busio
import terminalio
import digitalio
import displayio
import time

import random

import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS

from adafruit_display_text import label
from adafruit_st7735 import ST7735
from adafruit_st7735r import ST7735R


# The keyboard object!
time.sleep(1)  # Sleep for a bit to avoid a USB race condition on some systems
keyboard = Keyboard(usb_hid.devices)
keyboard_layout = KeyboardLayoutUS(keyboard)

# Release any resources currently in use for the displays
displayio.release_displays()

tft_cs = board.GP1
tft_dc = board.GP4
tft_sck = board.GP2
tft_mosi = board.GP3
tft_backlight = board.GP5

tft_miso = None
tft_size = {
    'width': 160,
    'height': 80
}

spi = busio.SPI(tft_sck, tft_mosi, tft_miso)

display_bus = displayio.FourWire(
    spi, command=tft_dc, chip_select=tft_cs
)

print('Making display...')
display = ST7735R(display_bus, width=tft_size['width'], height=tft_size['height'], rotation=270, colstart=26, rowstart=1, invert=True)
print('Done.')

print('Making display content...')

# Make the display context
splash = displayio.Group()
display.show(splash)

def create_sprite(color):
    color_bitmap = displayio.Bitmap(tft_size['width'], tft_size['height'], 1)
    color_palette = displayio.Palette(1)
    color_palette[0] = color
    sprite = displayio.TileGrid(color_bitmap, pixel_shader=color_palette, x=0, y=0)
    return sprite

class Colors:
    Black = 0x000000
    White = 0xFFFFFF
    Gray = 0x999999
    Red = 0xFF0000
    Green = 0x00FF00
    Blue = 0x0000FF
    Cyan = 0x00FFFF
    Magenta = 0xFF00FF
    Yellow = 0xFFFF00
    Purple = 0x9E42F5
    Orange = 0xE07D12

sprites = {
    'black': create_sprite(Colors.Black),
    'white': create_sprite(Colors.White),
    'gray': create_sprite(Colors.Gray),
    'red': create_sprite(Colors.Red),
    'green': create_sprite(Colors.Green),
    'blue': create_sprite(Colors.Blue),
    'yellow': create_sprite(Colors.Yellow),
    'magenta': create_sprite(Colors.Magenta),
    'cyan': create_sprite(Colors.Cyan),
    'purple': create_sprite(Colors.Purple),
    'orange': create_sprite(Colors.Orange),
}

# Display background
bg_sprite = create_sprite(Colors.Black)
splash.append(bg_sprite)

# Display text
output_text = label.Label(terminalio.FONT, text='', color=Colors.Gray, x=2, y=10, scale=1)
splash.append(output_text)

class InputState:
    RELEASED = 'RELEASED'
    PRESSING = 'PRESSING'
    HELD = 'HELD'
    RELEASING = 'RELEASING'

class KickInput:
    def __init__(self, pin, active_state, name):
        self.active_state = active_state
        self.name = name
        self.input = digitalio.DigitalInOut(pin)
        self.input.direction = digitalio.Direction.INPUT
        self._state = InputState.RELEASED

        # pull the opposite way of active
        if active_state == True:
            self.input.pull = digitalio.Pull.DOWN
        else:
            self.input.pull = digitalio.Pull.UP

    def set_callback(self, cb):
        self.callback = cb

    @property
    def state(self):
        return self._state

    @property
    def pressed(self):
        return self.input.value == self.active_state

    def update(self):
        changed = False
        if self.state == InputState.RELEASED:
            if self.pressed:
                self._state = InputState.PRESSING
                changed = True
        elif self.state == InputState.PRESSING:
            if self.pressed:
                self._state = InputState.HELD
                changed = True
            else:
                self._state = InputState.RELEASING
                changed = True
        elif self.state == InputState.HELD:
            if self.pressed == False:
                self._state = InputState.RELEASING
                changed = True
        elif self.state == InputState.RELEASING:
            if self.pressed == False:
                self._state = InputState.RELEASED
                changed = True
            else:
                self._state = InputState.PRESSING
                changed = True
        else:
            raise RuntimeError('Invalid state {0}'.format(self.state)) from exc

        if changed and self.callback != None:
            self.callback(self, self.state)

class KickSwitch(KickInput):

    def __init__(self, pin, name="Unknown", *, active_state=False):
        super().__init__(pin, active_state=active_state, name=name)


class JackSwitch():
    def __init__(self, drive_pin, switch0_pin, switch1_pin, name="Unknown"):
        # jack switches use their drive pin to
        # drive pin 0 or pin 1 high as active.
        self.dio_drive = digitalio.DigitalInOut(drive_pin)
        self.dio_drive.direction = digitalio.Direction.OUTPUT
        self.dio_drive.value = True

        jack_switch_active_state = self.dio_drive.value

        # use pull downs on the input so that they can be driven high
        switch0_name = '{0} 0'.format(name)
        self.switch0 = KickSwitch(switch0_pin, switch0_name, active_state=jack_switch_active_state)

        switch1_name = '{0} 1'.format(name)
        self.switch1 = KickSwitch(switch1_pin, switch1_name, active_state=jack_switch_active_state)

    def update(self):
        self.switch0.update()
        self.switch1.update()

    def set_callback(self, cb):
        self.switch0.set_callback(cb)
        self.switch1.set_callback(cb)

print('Creating kick switch DIOs...')

switches = (
    KickSwitch(board.GP6, 'Red'),
    KickSwitch(board.GP7, 'Blue'),
    KickSwitch(board.GP8, 'Yellow'),
    KickSwitch(board.GP9, 'Green')
)

print('Done.')

print('Creating jack switch DIOs...')

jack_left = JackSwitch(board.GP28, board.GP26, board.GP27, 'Left')
jack_right = JackSwitch(board.GP18, board.GP16, board.GP17, 'Right')

jacks = (
    jack_left,
    jack_right
)

print('Done.')

print('Creating debug whatevers...')

debug_a = board.GP10
debug_b = board.GP11
debug_c = board.GP12
debug_d = board.GP13

print('Done.')

print('Running...')

inputs = switches + jacks

switches[0].sprite = sprites['red']
switches[1].sprite = sprites['blue']
switches[2].sprite = sprites['yellow']
switches[3].sprite = sprites['green']
jacks[0].sprite = sprites['orange']
jacks[1].sprite = sprites['cyan']

activeKeymap = 0

def assign_sprite(s):
    if splash[0] != s:
        splash[0] = s

def assign_color_from_sprite(s):
    assign_color(s.pixel_shader[0])

def random_color():
    r = random.randint(0, 255)
    g = random.randint(0, 255)
    b = random.randint(0, 255)
    c = [ r, g, b ]
    assign_color(c)

def wheel(pos):
    # Input a value 0 to 255 to get a color value.
    # The colours are a transition r - g - b - back to r.
    if pos < 0 or pos > 255:
        return 0, 0, 0
    if pos < 85:
        return int(255 - pos * 3), int(pos * 3), 0
    if pos < 170:
        pos -= 85
        return 0, int(255 - pos * 3), int(pos * 3)
    pos -= 170
    return int(pos * 3), 0, int(255 - (pos * 3))

def assign_color(c):
    bg_sprite.pixel_shader[0] = c
    assign_sprite(bg_sprite)

def wheel_color(s):
    c = wheel(s)
    assign_color(c)

#def input_state_changed(input, state):
#    output_text.text = '{0}\n{1}!'.format(input.name, state)
#
#for i in inputs:
#    i.set_callback(input_state_changed)

def get_keymap(mode):
    global keymap
    return keymap[mode]

def get_active_keymap():
    global activeKeymap
    return get_keymap(activeKeymap)

def set_active_keymap(map):
    global keymap
    global activeKeymap
    if map >= 0 and map < len(keymap):
        activeKeymap = map
    return activeKeymap

def inject_keypress(state, keycode):
    if state == InputState.PRESSING:
        keyboard.press(keycode)
        print("Injecting key {0} press.".format(keycode))
    elif state == InputState.RELEASING:
        keyboard.release(keycode)
        print("Injecting key {0} release.".format(keycode))

def bind_input_to_keymap(input, index):
    input.set_callback(lambda input, state:
        inject_keypress(state, get_active_keymap()[index])
    )

def set_mode(input, mode):
    set_active_keymap(mode)
    km = get_active_keymap()
    output_text.text = "Active Mode:\n{0}\nKeymap:\n{1}".format(input.name, km)
    print("Switching to mode {0} ({1}). Keymap: {2}".format(input.name, mode, km))

def mode_callback(input, state, mode):
    if state == InputState.RELEASING:
        set_mode(input, mode)

def bind_input_to_mode(input, mode):
    input.set_callback(lambda input, state:
        mode_callback(input, state, mode)
    )

# Jacks are bound to keymaps
for i, jack in enumerate(jacks):
    bind_input_to_keymap(jack, i)

# Switches are bound to modes
for i, switch in enumerate(switches):
    bind_input_to_mode(switch, i)

# set default mode
set_mode(switches[0], 0)

while True:

    for i in inputs:
        i.update()

print('Done.')
