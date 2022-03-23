#!/usr/bin/env python
#
# Copyright (c) 2019, Pycom Limited.
#
# This software is licensed under the GNU GPL version 3 or any
# later version, with permitted additional terms. For more information
# see the Pycom Licence v1.0 document supplied with this file, or
# available at https://www.pycom.io/opensource/licensing
#

# system packages
import struct

# custom packages
from . import const as Const


def read_coils(starting_address, quantity):
    if not (1 <= quantity <= 2000):
        raise ValueError('invalid number of coils')

    return struct.pack('>BHH', Const.READ_COILS, starting_address, quantity)


def read_discrete_inputs(starting_address, quantity):
    if not (1 <= quantity <= 2000):
        raise ValueError('invalid number of discrete inputs')

    return struct.pack('>BHH', Const.READ_DISCRETE_INPUTS, starting_address, quantity)


def read_holding_registers(starting_address, quantity):
    if not (1 <= quantity <= 125):
        raise ValueError('invalid number of holding registers')

    return struct.pack('>BHH', Const.READ_HOLDING_REGISTERS, starting_address, quantity)


def read_input_registers(starting_address, quantity):
    if not (1 <= quantity <= 125):
        raise ValueError('invalid number of input registers')

    return struct.pack('>BHH', Const.READ_INPUT_REGISTER, starting_address, quantity)


def write_single_coil(output_address, output_value):
    if output_value not in [0x0000, 0xFF00]:
        raise ValueError('Illegal coil value')

    return struct.pack('>BHH', Const.WRITE_SINGLE_COIL, output_address, output_value)


def write_single_register(register_address, register_value, signed=True):
    fmt = 'h' if signed else 'H'

    return struct.pack('>BH' + fmt, Const.WRITE_SINGLE_REGISTER, register_address, register_value)


def write_multiple_coils(starting_address, value_list):
    sectioned_list = [value_list[i:i + 8] for i in range(0, len(value_list), 8)]

    output_value = []
    for index, byte in enumerate(sectioned_list):
        output = sum(v << i for i, v in enumerate(byte))
        output_value.append(output)

    fmt = 'B' * len(output_value)

    return struct.pack('>BHHB' + fmt, Const.WRITE_MULTIPLE_COILS, starting_address, len(value_list), ((len(value_list) - 1) // 8) + 1, *output_value)


def write_multiple_registers(starting_address, register_values, signed=True):
    quantity = len(register_values)

    if not (1 <= quantity <= 123):
        raise ValueError('invalid number of registers')

    fmt = ('h' if signed else 'H') * quantity
    return struct.pack('>BHHB' + fmt, Const.WRITE_MULTIPLE_REGISTERS, starting_address, quantity, quantity * 2, *register_values)


def validate_resp_data(data,
                       function_code,
                       address,
                       value=None,
                       quantity=None,
                       signed=True):
    if function_code in [Const.WRITE_SINGLE_COIL, Const.WRITE_SINGLE_REGISTER]:
        fmt = '>H' + ('h' if signed else 'H')
        resp_addr, resp_value = struct.unpack(fmt, data)

        if (address == resp_addr) and (value == resp_value):
            return True

    elif function_code in [Const.WRITE_MULTIPLE_COILS, Const.WRITE_MULTIPLE_REGISTERS]:
        resp_addr, resp_qty = struct.unpack('>HH', data)

        if (address == resp_addr) and (quantity == resp_qty):
            return True

    return False


def response(function_code,
             request_register_addr,
             request_register_qty,
             request_data,
             value_list=None,
             signed=True):
    if function_code in [Const.READ_COILS, Const.READ_DISCRETE_INPUTS]:
        output_value = []
        sectioned_list = [value_list[i:i + 8] for i in range(0, len(value_list), 8)]

        for index, byte in enumerate(sectioned_list):
            output = sum(v << i for i, v in enumerate(byte))
            output_value.append(output)

        fmt = 'B' * len(output_value)
        return struct.pack('>BB' + fmt, function_code, ((len(value_list) - 1) // 8) + 1, *output_value)

    elif function_code in [Const.READ_HOLDING_REGISTERS, Const.READ_INPUT_REGISTER]:
        quantity = len(value_list)

        if not (0x0001 <= quantity <= 0x007D):
            raise ValueError('invalid number of registers')

        if signed is True or signed is False:
            fmt = ('h' if signed else 'H') * quantity
        else:
            fmt = ''
            for s in signed:
                fmt += 'h' if s else 'H'

        return struct.pack('>BB' + fmt, function_code, quantity * 2, *value_list)

    elif function_code in [Const.WRITE_SINGLE_COIL, Const.WRITE_SINGLE_REGISTER]:
        return struct.pack('>BHBB', function_code, request_register_addr, *request_data)

    elif function_code in [Const.WRITE_MULTIPLE_COILS, Const.WRITE_MULTIPLE_REGISTERS]:
        return struct.pack('>BHH', function_code, request_register_addr, request_register_qty)


def exception_response(function_code, exception_code):
    return struct.pack('>BB', Const.ERROR_BIAS + function_code, exception_code)
