/* Host controller snapshot shared with win32u. GPL-3.0-or-later WITH the
 * Madeira Converter Exception, version 1; see LICENSE-EXCEPTION.md. */
#ifndef WINIOS_GAMEPAD_H
#define WINIOS_GAMEPAD_H
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif
#define WINIOS_GAMEPAD_MAX 4
struct winios_gamepad {
    uint32_t packet;
    uint16_t buttons;
    uint8_t left_trigger, right_trigger;
    int16_t lx, ly, rx, ry;
    uint8_t connected;
    uint8_t reserved[3];
};

/* NULL disconnects. The transport owns packet numbers; unchanged samples do
 * not advance them. All callers may run concurrently. No callbacks under lock. */
void winios_gamepad_set_state(int index, const struct winios_gamepad *state);
int winios_gamepad_get_state(int index, struct winios_gamepad *out);

/* ml2100: the opt-in HID controller (env.MADEIRA_PAD_MODE = hid). Player 1
 * only, served by the wineserver (build/wineserver/hidpad_ios.c) as a DualSense
 * or a generic HID gamepad; the XInput snapshot above is not involved and its
 * path is unchanged. The low 16 bits of `buttons` are the XINPUT_GAMEPAD_* bits
 * (so the XInput sample, touch merge included, carries over as is); the bits
 * above are what XInput cannot express. Sticks keep the XInput convention: full
 * signed range, +y is up. */
#define WINIOS_HIDPAD_TOUCHPAD 0x00010000u  /* DualSense touchpad click */
#define WINIOS_HIDPAD_MUTE     0x00020000u  /* DualSense microphone button */
#define WINIOS_HIDPAD_L2       0x00040000u  /* trigger past its digital threshold */
#define WINIOS_HIDPAD_R2       0x00080000u

#define WINIOS_HIDPAD_BATTERY_UNKNOWN 0xff

struct winios_hidpad {
    uint32_t packet;              /* transport-owned, as winios_gamepad */
    uint32_t buttons;
    int16_t lx, ly, rx, ry;
    uint8_t left_trigger, right_trigger;
    uint8_t connected;
    uint8_t battery;              /* 0-100, or WINIOS_HIDPAD_BATTERY_UNKNOWN */
    uint8_t charging;             /* 0 discharging, 1 charging, 2 full */
    uint8_t motion;               /* 1: gyro/accel below are live */
    uint8_t touch[2];             /* 1: finger down on touchpad point 0/1 */
    uint8_t reserved[2];
    uint16_t touch_x[2];          /* DualSense touchpad units, 0-1919 */
    uint16_t touch_y[2];          /* 0-1079 */
    int16_t gyro[3];              /* DualSense units (16 per deg/s, feature 0x05) */
    int16_t accel[3];             /* DualSense units (8192 per g) */
    uint16_t reserved2;           /* 48 bytes, no padding: the transport memcmp()s it */
};

/* What the game wrote to the pad (output report 0x02), newest state, for the
 * app to apply. `serial` advances on every change; *_valid say which parts the
 * game has set at least once. Rumble is the "compatible vibration" pair. */
struct winios_hidpad_output {
    uint32_t serial;
    uint8_t rumble_valid, rumble_left, rumble_right;
    uint8_t lightbar_valid, red, green, blue;
    uint8_t player_leds_valid, player_leds;
    uint8_t mute_led_valid, mute_led;
    uint8_t trigger_valid[2];     /* [0] left (L2), [1] right (R2) */
    uint8_t trigger[2][11];       /* the effect block as written: mode, then parameters */
    uint8_t reserved[5];          /* 44 bytes, no padding */
};

/* NULL disconnects (the device stays, at rest). Same locking rules as above. */
void winios_hidpad_set_state(const struct winios_hidpad *state);
int winios_hidpad_get_state(struct winios_hidpad *out);
void winios_hidpad_set_output(const struct winios_hidpad_output *output);
/* Copies the latest output into *out and returns 1 when its serial differs
 * from `seen`, else 0. */
int winios_hidpad_get_output(uint32_t seen, struct winios_hidpad_output *out);
#ifdef __cplusplus
}
#endif
#endif
