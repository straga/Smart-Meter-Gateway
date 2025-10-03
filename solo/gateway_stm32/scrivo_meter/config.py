# STM32 Blackpill F411 Configuration
# UART configuration (pins are fixed by UART number on STM32)

METER_UART_ID = 1   # UART1 (PA9/PA10) → Eastron meter
PANEL_UART_ID = 2   # UART2 (PA2/PA3)  → Solax panel


data_request = {
    "watt_eastron_1p": {
        "addr": 1,
        "func": 4,
        "start_reg": 12,
        "qty_reg": 2,
        "alive": 0,
        "raw": 0x00,
    },

    "watt_chint_1p": {
        "addr": 1,
        "func": 3,
        "start_reg": 8192,
        "qty_reg": 6,
        "alive": 0,
        "raw": 0x00,
    }
}

data_register_master = {
    # eastron watt : reply from "addr": 1, "func": 4, "start_reg": 12, "qty_reg": 2: - act for convert to float watt
    30013: {
        "alive": 0,
        "raw": b'\x00',
        "value": 0,
        "act": {"unpack": ">f", "scale": 1, "unit": "W", },
    },

    # deye chint 1p : reply from "addr": 1, "func": 3, "start_reg": 8192, "qty_reg": 6: leave as is for Deye invertor
    48193: {
        "alive": 0,
        "raw": b'\x00',
        "value": 0,
        "act": None,
    },
}


data_register_slave = {

    # solax ask from: func 03 , 00 0e = 14+1 = offset 40015:    Solax ask Int : need convert from float to int
    40015: {
        "master": 30013,
        "func": 0x03,
        "act": {"pack": ">h", "scale": 1, "data_type": "int"}
    },

    # solax ask from: func 03,  00 0b = 11+1 = offset 40012:    Solax ask init.
    40012: {
        "master": -1,
        "func": 0x03,
        "act": {"pack": ">h", "scale": 1, "value": 0}
    },

    # solax ask from: func 03, 8+1 =           offset 40009:    Solax ask init.
    40009: {
        "master": -1,
        "func": 0x03,
        "act": {"pack": ">h", "scale": 1, "value": 0}
    },

    # daye ask from: func 03, 00 0e = 14+1 = offset 48193:      Deye ask watts send as is.
    48193: {
        "master": 48193,
        "func": 0x03,
        "act": None
    },

    # Solax Bost: func 04, reg 12 = offset 30013: Active Power (direct read)
    30013: {
        "master": 30013,
        "func": 0x04,
        "act": None  # Send raw data (float32) as-is
    },

    # Solax Boost: func 03, reg 21 = offset 40022: Holding Register 21 (unknown, send 0)
    40022: {
        "master": -1,
        "func": 0x03,
        "act": {"pack": ">I", "scale": 1, "value": 0}  # 4 bytes (2 registers) = 0
    },
}

panel_slave_addr = [1]
