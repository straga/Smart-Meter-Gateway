# This file is executed on every boot (including wake-boot from deepsleep)
#import esp
#esp.osdebug(None)
#import webrepl
#webrepl.start()

# Disable REPL/logging on UART - use only USB VCP
import pyb
pyb.repl_uart(None)  # Disable UART for REPL, use only USB
