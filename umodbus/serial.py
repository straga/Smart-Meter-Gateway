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
from machine import UART
from machine import Pin
import struct
import time
import machine

# custom packages
from . import const as Const
from . import functions
from .common import Request
from .common import ModbusException


class Serial(object):
    def __init__(self,
                 uart_id=1,
                 baudrate=9600,
                 data_bits=8,
                 stop_bits=1,
                 parity=None,
                 pins=None,
                 ctrl_pin=None,
                 name=None):
        self._uart = UART(uart_id,
                          baudrate=baudrate,
                          bits=data_bits,
                          parity=parity,
                          stop=stop_bits,
                          # timeout_chars=2,  # WiPy only
                          # pins=pins         # WiPy only
                          # tx=pins[0],
                          # rx=pins[1]
                          )
        self.name = name
        if ctrl_pin is not None:
            self._ctrlPin = Pin(ctrl_pin, mode=Pin.OUT)
        else:
            self._ctrlPin = None

        if baudrate <= 19200:
            # 4010us (approx. 4ms) @ 9600 baud
            self._t35chars = (3500000 * (data_bits + stop_bits + 2)) // baudrate
        else:
            self._t35chars = 1750   # 1750us (approx. 1.75ms)

    def _calculate_crc16(self, data):
        crc = 0xFFFF

        for char in data:
            crc = (crc >> 8) ^ Const.CRC16_TABLE[((crc) ^ char) & 0xFF]

        return struct.pack('<H', crc)

    def _bytes_to_bool(self, byte_list):
        bool_list = []

        for index, byte in enumerate(byte_list):
            bool_list.extend([bool(byte & (1 << n)) for n in range(8)])

        return bool_list

    def _to_short(self, byte_array, signed=True):
        response_quantity = int(len(byte_array) / 2)

        # fmt = '>' + (('h' if signed else 'H') * response_quantity)
        # return struct.unpack(fmt, byte_array)

        data = struct.unpack('>f', byte_array)
        if len(data) == 1:
            return data[0]

        return data



    def _exit_read(self, response):
        if response[1] >= Const.ERROR_BIAS:
            if len(response) < Const.ERROR_RESP_LEN:
                return False
        elif (Const.READ_COILS <= response[1] <= Const.READ_INPUT_REGISTER):
            expected_len = Const.RESPONSE_HDR_LENGTH + 1 + response[2] + Const.CRC_LENGTH
            if len(response) < expected_len:
                return False
        elif len(response) < Const.FIXED_RESP_LEN:
            return False

        return True

    def _uart_read(self):
        response = bytearray()

        for x in range(1, 40):
            if self._uart.any():
                # WiPy only
                # response.extend(self._uart.readall())
                response.extend(self._uart.read())

                # variable length function codes may require multiple reads
                if self._exit_read(response):
                    break
            time.sleep(0.05)

        return response

    def _uart_read_frame(self, timeout=None):
        received_bytes = bytearray()

        # set timeout to at least twice the time between two frames in case the
        # timeout was set to zero or None
        if timeout == 0 or timeout is None:
            timeout = 2 * self._t35chars  # in milliseconds

        start_us = time.ticks_us()

        # stay inside this while loop at least for the timeout time
        while (time.ticks_diff(time.ticks_us(), start_us) <= timeout):
            # check amount of available characters
            if self._uart.any():
                # remember this time in microseconds
                last_byte_ts = time.ticks_us()

                # do not stop reading and appending the result to the buffer
                # until the time between two frames elapsed
                while time.ticks_diff(time.ticks_us(), last_byte_ts) <= self._t35chars:
                    # WiPy only
                    # r = self._uart.readall()
                    r = self._uart.read()

                    # if something has been read after the first iteration of
                    # this inner while loop (during self._t35chars time)
                    if r is not None:
                        # append the new read stuff to the buffer
                        received_bytes.extend(r)

                        # update the timestamp of the last byte being read
                        last_byte_ts = time.ticks_us()

            # if something has been read before the overall timeout is reached
            if len(received_bytes) > 0:
                # return received_bytes
                break

        # return the result in case the overall timeout has been reached
        if len(received_bytes) > 0:
            print("  ")

            pdu_hex = ' '.join('{:02x}'.format(x) for x in received_bytes)

            print(f" << uart({self.name}: {pdu_hex} - frame")


        return received_bytes

    def _send(self, modbus_pdu, slave_addr):
        serial_pdu = bytearray()
        serial_pdu.append(slave_addr)

        serial_pdu.extend(modbus_pdu)

        crc = self._calculate_crc16(serial_pdu)

        serial_pdu.extend(crc)

        if self._ctrlPin:
            self._ctrlPin(1)

        self._uart.write(serial_pdu)

        if self._ctrlPin:
            while not self._uart.wait_tx_done(2):
                machine.idle()
            time.sleep_us(self._t35chars)
            self._ctrlPin(0)

        pdu_hex = ' '.join('{:02x}'.format(x) for x in serial_pdu)
        print(f" >> uart({self.name}) : {pdu_hex}")


    def _send_receive(self, modbus_pdu, slave_addr, count):
        # flush the Rx FIFO
        self._uart.read()
        self._send(modbus_pdu, slave_addr)

        return self._validate_resp_hdr(self._uart_read(), slave_addr, modbus_pdu[0], count)

    def _validate_resp_hdr(self, response, slave_addr, function_code, count):
        if len(response) == 0:
            raise OSError('no data received from slave')

        resp_crc = response[-Const.CRC_LENGTH:]
        expected_crc = self._calculate_crc16(response[0:len(response) - Const.CRC_LENGTH])

        if ((resp_crc[0] is not expected_crc[0]) or (resp_crc[1] is not expected_crc[1])):
            raise OSError('invalid response CRC')

        if (response[0] != slave_addr):
            raise ValueError('wrong slave address')

        if (response[1] == (function_code + Const.ERROR_BIAS)):
            raise ValueError('slave returned exception code: {:d}'.
                             format(response[2]))

        hdr_length = (Const.RESPONSE_HDR_LENGTH + 1) if count else Const.RESPONSE_HDR_LENGTH

        return response[hdr_length:len(response) - Const.CRC_LENGTH]

    def read_coils(self, slave_addr, starting_addr, coil_qty):
        modbus_pdu = functions.read_coils(starting_addr, coil_qty)

        resp_data = self._send_receive(modbus_pdu, slave_addr, True)
        status_pdu = self._bytes_to_bool(resp_data)

        return status_pdu

    def read_discrete_inputs(self, slave_addr, starting_addr, input_qty):
        modbus_pdu = functions.read_discrete_inputs(starting_addr, input_qty)

        resp_data = self._send_receive(modbus_pdu, slave_addr, True)
        status_pdu = self._bytes_to_bool(resp_data)

        return status_pdu

    def read_holding_registers(self,
                               slave_addr,
                               starting_addr,
                               register_qty,
                               signed=True):
        modbus_pdu = functions.read_holding_registers(starting_addr, register_qty)

        resp_data = self._send_receive(modbus_pdu, slave_addr, True)

        # print(resp_data)

        register_value = self._to_short(resp_data, signed)

        return register_value

    def read_input_registers(self,
                             slave_addr,
                             starting_addr,
                             register_qty,
                             signed=True):
        modbus_pdu = functions.read_input_registers(starting_addr,
                                                    register_qty)

        resp_data = self._send_receive(modbus_pdu, slave_addr, True)

        register_value = self._to_short(resp_data, signed)

        raw_hex = ' '.join('{:02x}'.format(x) for x in resp_data)
        print(f" << uart({self.name}) : {raw_hex} = {register_value}")
        return register_value

    def write_single_coil(self, slave_addr, output_address, output_value):
        modbus_pdu = functions.write_single_coil(output_address, output_value)

        resp_data = self._send_receive(modbus_pdu, slave_addr, False)
        operation_status = functions.validate_resp_data(resp_data,
                                                        Const.WRITE_SINGLE_COIL,
                                                        output_address,
                                                        value=output_value,
                                                        signed=False)

        return operation_status

    def write_single_register(self,
                              slave_addr,
                              register_address,
                              register_value,
                              signed=True):
        modbus_pdu = functions.write_single_register(register_address,
                                                     register_value,
                                                     signed)

        resp_data = self._send_receive(modbus_pdu, slave_addr, False)
        operation_status = functions.validate_resp_data(resp_data,
                                                        Const.WRITE_SINGLE_REGISTER,
                                                        register_address,
                                                        value=register_value,
                                                        signed=signed)

        return operation_status

    def write_multiple_coils(self,
                             slave_addr,
                             starting_address,
                             output_values):
        modbus_pdu = functions.write_multiple_coils(starting_address,
                                                    output_values)

        resp_data = self._send_receive(modbus_pdu, slave_addr, False)
        operation_status = functions.validate_resp_data(resp_data,
                                                        Const.WRITE_MULTIPLE_COILS,
                                                        starting_address,
                                                        quantity=len(output_values))

        return operation_status

    def write_multiple_registers(self,
                                 slave_addr,
                                 starting_address,
                                 register_values,
                                 signed=True):
        modbus_pdu = functions.write_multiple_registers(starting_address,
                                                        register_values,
                                                        signed)

        resp_data = self._send_receive(modbus_pdu, slave_addr, False)
        operation_status = functions.validate_resp_data(resp_data,
                                                        Const.WRITE_MULTIPLE_REGISTERS,
                                                        starting_address,
                                                        quantity=len(register_values))

        return operation_status

    def send_response(self,
                      slave_addr,
                      function_code,
                      request_register_addr,
                      request_register_qty,
                      request_data,
                      values=None,
                      signed=True):

        print(f"val: {values}")
        modbus_pdu = functions.response(function_code,
                                        request_register_addr,
                                        request_register_qty,
                                        request_data,
                                        values,
                                        signed)

        self._send(modbus_pdu, slave_addr)

    def send_exception_response(self,
                                slave_addr,
                                function_code,
                                exception_code):
        modbus_pdu = functions.exception_response(function_code,
                                                  exception_code)
        self._send(modbus_pdu, slave_addr)

    def get_request(self, unit_addr_list, timeout=None):
        req = self._uart_read_frame(timeout)

        if len(req) < 8:
            return None

        if req[0] not in unit_addr_list:
            return None

        reg_data = req[:8]

        pdu_hex = ' '.join('{:02x}'.format(x) for x in reg_data)
        print(f" << uart({self.name}): {pdu_hex} - data")

        req = reg_data

        req_crc = req[-Const.CRC_LENGTH:]
        req_no_crc = req[:-Const.CRC_LENGTH]
        expected_crc = self._calculate_crc16(req_no_crc)



        if (req_crc[0] != expected_crc[0]) or (req_crc[1] != expected_crc[1]):
            print("frame data = crc error")
            print(f"crc: {req_crc}")
            print(f"no_crc: {req_no_crc}")
            print(f"e_crc: {expected_crc}")
            return None

        try:
            request = Request(self, req_no_crc)
        except ModbusException as e:
            self.send_exception_response(req[0],
                                         e.function_code,
                                         e.exception_code)
            print(f"err frame data:  {e}")
            return None

        return request
