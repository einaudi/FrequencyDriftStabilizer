import src.DAC.AD9912_lib.config as config
import RPi.GPIO as GPIO


I_DAC_REF = 0.120

addr_config = 0x0000
addr_readBuffer = 0x0004
addr_regUpdate = 0x0005
addr_power = 0x0010
addr_Ndiv = 0x0020

# frequency
addr_FTW0 = 0x01A6
addr_FTW1 = 0x01A7
addr_FTW2 = 0x01A8
addr_FTW3 = 0x01A9
addr_FTW4 = 0x01AA
addr_FTW5 = 0x01AB

# amplitude
addr_DAC0 = 0x040B
addr_DAC1 = 0x040C

class AD9912():

    def __init__(self):
        self._cs_pin = config.CS_PIN
        self._upd_pin = config.UPD_PIN
        self._reset_pin = config.RESET_PIN

        config.module_init()
        # config.SPI_init()

        self._f_s = 1000.

        # reset DDS
        config.digital_write(self._reset_pin, GPIO.HIGH)
        config.delay_ms(1)
        config.digital_write(self._reset_pin, GPIO.LOW)

        # reference
        self.setRef(100.)

        # active SDO
        config.digital_write(self._cs_pin, GPIO.LOW)#cs  0
        config.spi_writebyte([((addr_config & 0xFF00) | 0x6000) >> 8, addr_config & 0x00FF])
        config.spi_writebyte([0x18])
        config.digital_write(self._cs_pin, GPIO.HIGH)#cs  0

        # N-divider init
        config.digital_write(self._cs_pin, GPIO.LOW)#cs  0
        config.spi_writebyte([((addr_Ndiv & 0xFF00) | 0x6000) >> 8, addr_Ndiv & 0x00FF])
        config.spi_writebyte([0x03])
        config.digital_write(self._cs_pin, GPIO.HIGH)#cs  0

        self.setFrequency(0)
        self.setAmp(20)

    def setFrequency(self, f):

        if f > 400.:
            f = 400.

        ftw = int(f/self._f_s * pow(2, 48))
        ftw = split_into_bytes(ftw, 6)

        config.digital_write(self._cs_pin, GPIO.LOW)#cs  0

        # write ftw using streaming mode
        config.spi_writebyte([((addr_FTW0 & 0xFF00) | 0x6000) >> 8, addr_FTW0 & 0x00FF] + ftw)
        # config.spi_writebyte(ftw)

        # write ftw byte by byte
        # # send FTW0
        # config.spi_writebyte([addr_DAC0 & 0x00FF, ((addr_DAC0 & 0xFF00) >> 8)])
        # config.spi_writebyte([ftw[0]])
        # # send FTW1
        # config.spi_writebyte([addr_DAC1 & 0x00FF, ((addr_DAC1 & 0xFF00) >> 8)])
        # config.spi_writebyte([ftw[1]])
        # # send FTW2
        # config.spi_writebyte([addr_DAC1 & 0x00FF, ((addr_DAC1 & 0xFF00) >> 8)])
        # config.spi_writebyte([ftw[2]])
        # # send FTW3
        # config.spi_writebyte([addr_DAC1 & 0x00FF, ((addr_DAC1 & 0xFF00) >> 8)])
        # config.spi_writebyte([ftw[3]])
        # # send FTW4
        # config.spi_writebyte([addr_DAC1 & 0x00FF, ((addr_DAC1 & 0xFF00) >> 8)])
        # config.spi_writebyte([ftw[4]])
        # # send FTW5
        # config.spi_writebyte([addr_DAC1 & 0x00FF, ((addr_DAC1 & 0xFF00) >> 8)])
        # config.spi_writebyte([ftw[5]])

        config.digital_write(self._cs_pin, GPIO.HIGH)#cs  0

        self._update_pulse()
    
    def setAmp(self, amp):

        if amp < 0:
            amp = 0
        if amp > 100:
            amp = 100

        i_dac = 0.231*amp + 8.6
        fsc = int(1024/192 * (i_dac/I_DAC_REF - 72))
        fsc = split_into_bytes(fsc, 2)

        config.digital_write(self._cs_pin, GPIO.LOW)#cs  0

        config.spi_writebyte([((addr_DAC0 & 0xFF00) | 0x6000) >> 8, addr_DAC0 & 0x00FF])
        config.spi_writebyte(fsc)

        config.digital_write(self._cs_pin, GPIO.HIGH)#cs  0

    def setRef(self, ref):

        if ref == 100:
            self._f_s = 1000
            msg = [0xC0]
        elif ref == 250 or ref == 1000:
            self._f_s = ref
            msg = [0xD0]
        else:
            return

        config.digital_write(self._cs_pin, GPIO.LOW)#cs  0

        config.spi_writebyte([(addr_power & 0xFF00) >> 8, addr_power & 0x00FF])
        config.spi_writebyte(msg)

        config.digital_write(self._cs_pin, GPIO.HIGH)#cs  0

    def _update_pulse(self):

        # Update pulse
        config.digital_write(self._upd_pin, GPIO.HIGH)
        # delay?
        config.delay_ms(0.001)
        config.digital_write(self._upd_pin, GPIO.LOW)

    def getFrequency(self):

        config.digital_write(self._cs_pin, GPIO.LOW)#cs  0
        config.spi_writebyte([((addr_FTW0 & 0xFF00) | 0xE000) >> 8, addr_FTW0 & 0x00FF])
        ret = config.spi_readbytes(6)
        config.digital_write(self._cs_pin, GPIO.HIGH)#cs  0

        return ret

class AD9912_STM32():

    def __init__(self):

        self._cs_pin = config.CS_PIN

        config.module_init()
        config.SPI_init()

        # self.setFrequency(0)
        self.setAmp(20)

    def setFrequency(self, f):

        if f > 400.:
            f = 400.

        msg = 'F{:13.9f}'.format(f).encode('utf-8')
        msg = [item for item in msg]

        config.digital_write(self._cs_pin, GPIO.LOW)#cs  0
        config.spi_writebyte(msg)
        config.digital_write(self._cs_pin, GPIO.HIGH)#cs  0

    def setAmp(self, amp):

        if amp < 0:
            amp = 0
        if amp > 100:
            amp = 100

        amp = 0.231*amp + 8.6

        msg = 'A{:13.9f}'.format(amp).encode('utf-8')
        msg = [item for item in msg]

        config.digital_write(self._cs_pin, GPIO.LOW)#cs  0
        config.spi_writebyte(msg)
        config.digital_write(self._cs_pin, GPIO.HIGH)#cs  0

    def setRef(self, ref):

        msg = 'R{:13.9f}'.format(ref).encode('utf-8')
        msg = [item for item in msg]

        config.digital_write(self._cs_pin, GPIO.LOW)#cs  0
        config.spi_writebyte(msg)
        config.digital_write(self._cs_pin, GPIO.HIGH)#cs  0


def split_into_bytes_48(value):

    ret = []
    ret.append(value & 0x0000000000FF)
    ret.append((value & 0x00000000FF00) >> 8)
    ret.append((value & 0x000000FF0000) >> 16)
    ret.append((value & 0x0000FF000000) >> 24)
    ret.append((value & 0x00FF00000000) >> 32)
    ret.append((value & 0xFF0000000000) >> 40)

    ret = []

    return ret

def split_into_bytes_2(value):

    ret = []
    ret.append(value & 0x00FF)
    ret.append((value & 0xFF00) >> 8)

def split_into_bytes(value, B=2):

    ret = []
    for i in range(B):
        ret.append((value >> 8*i) & 0xFF)

    return ret