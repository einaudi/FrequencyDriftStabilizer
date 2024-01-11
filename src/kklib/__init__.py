"""
Give access to native K+K library on Windows and Linux Systems

Depending on System Platform the following libraries are requested:
    Windows:
        64 bit: KK_Library_64.dll
        32 bit: KK_FX80E.dll
    Linux:
        64 bit: libkk_library_64_cdecl.so
        32 bit: libkk_library_32_cdecl.so

created 20.02.2019

@author: Loryn Brendes

History

version date        description
1.0     2019-02-20  created
1.0.1   2020-03-24  correction: platform.architecture() 
                    explicit c_int32
                    KK-Library min version 18.1.5
        2020-03-25  windows only
1.0.2   2020-04-08  KK-Library min version 18.1.6
1.0.3   2020-10-12  Linux support  
                    KK-Library min version 18.1.10
                    report_TCP_log: NSZ log types added
                    open_TCP_log: NSZ modes added
                    renamed: set_decimal_separator
                    added:
                        KK_ERR_NOT_SUPPORTED
                        get_firmware_version
                        has_FRAM
                        set_NSZ_calibration_data
                        remote_login 
1.0.4   2021-02-08  KK-Library min version 18.2.4
                    open_TCP_log: PHASEPREDECESSORLOG, USERLOG1, USERLOG2 added
1.1.0   2021-05-28  KK-Library min version 19.0.2
                    added:
                        KK_Err_Reconnected
                        open_TCP_log_time
                    changed:
                        stop_save_report_data without parameter dbg_id 
1.2     2021-11-18  KK-Library min version 19.1.2
                    added:
                        is_serial_device
                        get_FHR_settings, set_FHR_settings
                        helper classes FHRData, FHRSettings
1.3     2022-01-05  KK-Library min version 19.2.0
                    added:
                        open_TCP_log_type
                        send_TCP_data
1.4     2022.10.09  KK-Library min version 19.3.0
                    send_TCP_data delivers response
1.5     2023.01.04  KK-Library min version 19.3.1
                    added:
                        get_device_start_state
                        set_send_7016
"""
from builtins import str

__all__ = ['NativeLib', 'NativeLibError', 'ErrorCode', 'KK_Result', 'DebugLogType', 'FHRData', 'FHRSettings']
__version__ = '1.5'

import ctypes
from ctypes import c_byte, c_char_p, c_int32, c_uint, c_bool, c_char, byref,\
    c_ulong
from enum import Enum
import locale
import platform
import sys


#-------------------------------------------------------------------------
# Library exception class
#-------------------------------------------------------------------------

class NativeLibError(Exception):
    """Exception class for Exceptions thrown by class NativeLib."""
    pass


#-------------------------------------------------------------------------
# Library return class
#-------------------------------------------------------------------------

# Enumerate error codes
class ErrorCode(Enum):
    """Enumeration of error codes, used in KK_Result.result_code
    """
    KK_NO_ERR = 0
    # successful operation
    
    KK_ERR = 1
    # operation failed
    
    KK_ERR_ENUM_SERIAL = 2
    # Enumeration of serial ports failed
   
    KK_ERR_ENUM_USB = 3
    # Enumeration of USB devices failed

    KK_ERR_ENUM_SERIAL_USB = 4
    # Enumeration of serial ports and USB devices failed
        
    KK_ERR_BUFFER_TOO_SMALL = 5
    # String in KK_Result.data truncated to 1024 character
        
    KK_ERR_BUFFER_OVERFLOW = 6
    # Lost of data occurred. App does not read fast enough

    KK_ERR_WRITE = 7
    # Writing via current connection failed
        
    KK_ERR_SERVER_DOWN = 8
    # Connection to K+K server has broken, server is down
        
    KK_ERR_DEVICE_NOT_CONNECTED = 9
    # Connection to K+K device is interrupted (no usb cable)
        
    KK_HARDWARE_FAULT = 10
    # K+K device does not send measurement data. Measurement hardware 
    # should be checked.
    # Connection to K+K device is closed.
    # KK_Result.data contains error message
        
    KK_PARAM_ERROR = 11
    # Parameter in function call has invalid value
        
    KK_CMD_IGNORED = 12
    # Command rejected (no connection, waiting queue full)
    
    KK_ERR_NOT_SUPPORTED = 13
    # Called function is not supported by K+K device
    
    KK_ERR_RECONNECTED = 14
    # Reconnection of an interrupted connection
        
        
class KK_Result:
    """Result class returned by most NativeLib methods
    """
    result_code: ErrorCode
    """Operation result code (value of ErrorCode)
    """
    data: str
    """Operation string result or error message, 
    if result_Code != KK_NO_ERR
    """
    int_value: int
    """Operation int value, set by some methods
    (e.g. start_TCP_server)
    """
        
    def __init__(self):
        """Initialize no error results"""
        self.result_code = ErrorCode.KK_NO_ERR
        self.data = None
        self.int_value = 0

    
#-------------------------------------------------------------------------
# Error strings from native library
#-------------------------------------------------------------------------

_ERR_SOURCE_NOT_FOUND = "Source-ID "


#-------------------------------------------------------------------------
# Maximal channel count 
#-------------------------------------------------------------------------

KK_MAX_CHANNELS = 24
               
#-------------------------------------------------------------------------
# DebugLogType
#-------------------------------------------------------------------------

class DebugLogType(Enum):
    """Defines debug log types for method NativeLib.set_debug_log_limit
    Specifies file management of debug output files.
    """
    LOG_UNLIMITED = 0
    # All debug outputs are written to the same file, reopen overwrites 
    # existing debug file.
    # File size is unlimited. Default value

    LOG_OVERWRITE = 1
    # All debug outputs are written to the same file, reopen overwrites 
    # existing debug file.
    # File size is limited. If size is reached old debug outputs will 
    # be overwritten.

    LOG_CREATE_NEW = 2
    # A new debug file is created, filename is appended by date and 
    # time stamp.
    # File size is limited. If size is reached a new file is created.


#-------------------------------------------------------------------------
# FHR settings: helper classes for get_FHR_seetings, set_FHR_sttings
#-------------------------------------------------------------------------

class FHRData:
    """Defines FHR setting for one channel
    """
    NominalFreq: str
    LOFreq: str
    enabled: bool
    
    def __init__(self, s: str = ""):
        if not self.from_string(s):
            raise NativeLibError("Invalid string representation of FHRData: "+s)
        
    def clear(self):
        self.NominalFreq = '0'
        self.LOFreq = '0'
        self.enabled = False

    def to_string(self) -> str:
        """Returns string representation of FHRData
        """
        if self.enabled:
            s = '1'
        else:
            s = '0'
        return self.NominalFreq+';'+self.LOFreq+';'+s        

    def from_string(self, s: str = "") -> bool:
        """Converts string representation to FHRData
        @param s: string representation of FHRData or empty string
        @return: True, if s is a valid string representation
        """
        self.clear()
        if s == "":
            return True
        else:
            l_ = s.split(';')
            if len(l_) < 3:
                return False
            self.NominalFreq = l_[0]
            self.LOFreq = l_[1]
            if l_[2] == '0':
                self.enabled = False
            else:
                self.enabled = True
            return True

 
class FHRSettings:
    """Defines FHR settings for KK_MAX_CHANNELS
    """
    FHRChannels = [FHRData() for i in range(1, KK_MAX_CHANNELS)]
    
    def __init__(self, s: str = ""):
        if not self.from_string(s):
            raise NativeLibError("Invalid string representation of FHRSettings: "+s)

    def clear(self):
        for fhr in self.FHRChannels:
            fhr.clear()
    
    def to_string(self) -> str:
        """Returns string representation of FHRSettings
        """
        s = self.FHRChannels[0].to_string()
        for i in range(2, KK_MAX_CHANNELS):
            s = s+'/'+self.FHRChannels[i-1].to_string()
        return s
    
    def from_string(self, s: str) -> bool:
        """Converts string representation to FHRSettings
        @param s: string representation of FHRSettings or empty string
        @return: True, if s is a valid string representation
        """
        self.clear()
        aBool = True

        if s == "":
            return aBool
        else:
            # split into channel strings                
            l_ = s.split('/')
            limit = len(l_)
            if limit > KK_MAX_CHANNELS:
                limit = KK_MAX_CHANNELS
            
            for i in range(1, limit):
                if not self.FHRChannels[i-1].from_string():
                    aBool = False
                
            return aBool
            
    
#-------------------------------------------------------------------------
# Library class
#-------------------------------------------------------------------------

class NativeLib:
    """Wrapper class to access native K+K Library on Windows and Linux
    Needs minimum version 18.0 of K+K Library, throws NativeLibError else
    """
    
    #-------------------------------------------------------------------------
    # private variables
    #-------------------------------------------------------------------------

    _kkdll = None
    _buffer = bytearray(1024)
    
    #-------------------------------------------------------------------------
    # decode bytearray
    #-------------------------------------------------------------------------

    def _bytearray2string(self, barray: bytearray) -> str:
        # string in bytearray is terminated by 0
        if barray[0] == 0:
            return None
        else:
            i = barray.index(0);
            hilf = barray[:i];
            return hilf.decode()
    
    #-------------------------------------------------------------------------
    # constructor
    #-------------------------------------------------------------------------

    # load native library
    def _load_library(self):
        # different library names for windows and linux
        _libname = ""
        _bits = ''
        _linkage = ''
        (_bits, _linkage) = platform.architecture()
        
        if platform.system() == "Windows":
            if _bits.startswith('64'):
                _libname = "KK_Library_64.dll"
            else:
                _libname = "KK_FX80E.dll"
        else:
            # Linux
            if _bits.startswith('64'):
                _libname = "libkk_library_64_cdecl.so"
            else:
                _libname = "libkk_library_32_cdecl.so"

        # load K+K library
        if _libname == "":
            raise NativeLibError("Unsupported platform: "+platform.system())
        else:
            try:
                if platform.system() == "Windows":
                    # library exports functions as stdcall -> use ctypes.windll
                    return ctypes.windll.LoadLibrary(_libname)
                else:
                    # library exports functions as cdecl -> use ctypes.cdll
                    return ctypes.cdll.LoadLibrary(_libname)
            except OSError as exc:
                raise NativeLibError("loading K+K library ("+_libname
                                     +") failed: "+str(exc))
    
    # class init
    def __init__(self):
        self._kkdll = self._load_library()
        # check version minimum 19.2.0 required
        version = self.get_version()
        errorVersion = "Invalid version "+version+", needs 19.3.1"
        subVersion = version
        indexdot = subVersion.find('.')
        if indexdot < 0:
            verNum = int(subVersion)
        else:
            verNum = int(subVersion[:indexdot])
        if verNum < 19:
            raise NativeLibError(errorVersion)
        doCheck = (verNum == 19)
        if doCheck:
            subVersion = subVersion[indexdot+1:]
            indexdot = subVersion.find('.')
            if indexdot < 0:
                verNum = int(subVersion)
            else:
                verNum = int(subVersion[:indexdot])
            if verNum < 3:
                raise NativeLibError(errorVersion)
            doCheck = (verNum == 3)
        if doCheck:
            subVersion = subVersion[indexdot+1:]
            # separator blank!
            indexdot = subVersion.find(' ')
            if indexdot < 0:
                verNum = int(subVersion)
            else:
                verNum = int(subVersion[:indexdot])
            if verNum < 1:
                raise NativeLibError(errorVersion)
        # set default locale
        locale.setlocale(locale.LC_ALL, '')
            
                
    #-------------------------------------------------------------------------
    # Multiple source connections
    #-------------------------------------------------------------------------
    
    def get_source_id(self) -> int:
        """Get new source id from native K+K library.
        For details see CreateMultiSource in K+K library manual.
        """
        sourceId = c_int32(self._kkdll.CreateMultiSource())
        return sourceId.value
        
        
    #-------------------------------------------------------------------------
    # Enumerate
    #-------------------------------------------------------------------------
    
    ENUM_FLAG_SERIAL_PORTS = 1
    # enumerate serial ports only
    
    ENUM_FLAG_USB = 2
    # enumerate K+K devices found on USB
    
    ENUM_FLAG_LOCAL_DEVICES = 3
    # enumerate serial ports and K+K devices on USB
     
    def enumerate_Devices(self, enum_flags: int) -> KK_Result:
        """Enumerates serial ports and/or K+K devices found on USB, depending on
        enum_flags.
        Found serial port names and USB devices names are returned in KK_Result.data
        separated by comma (,). 
        When no names are found KK_Result.data is None.
        If an error occurs, KK_Result.data contains error message.
        For details see Multi_EnumerateDevices in K+K library manual.
        @param enumFlags specifies what is to be enumerated: ENUM_FLAG_SERIAL_PORTS,
        ENUM_FLAG_USB, ENUM_FLAG_LOCAL_DEVICES 
        @return see KK_Result.result_code
        KK_NO_ERR: KK_Result.data contains found names separated by comma (,) or
        is None, if no serial ports and/or USB devices were found.
        all other codes are error numbers and KK_Result.data contains 
        error message:
        ENUM_FLAG_SERIAL_PORTS, ENUM_FLAG_USB, ENUM_FLAG_LOCAL_DEVICES: specified
        enumeration failed
        """
        # check parameter values
        kkres = KK_Result()
        if (enum_flags < 0) or (enum_flags > 3):
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
            kkres.data = "Invalid enum_Flags, must be 1..3"
            return kkres
        flags_ = c_byte(enum_flags)
        # mutable 1024 bytes buffer needed
        char_array = ctypes.c_char * len(self._buffer)
        retI = c_int32(self._kkdll.Multi_EnumerateDevices(
                char_array.from_buffer(self._buffer), flags_))
        if retI.value == 0: 
            kkres.data = self._bytearray2string(self._buffer);
        else:
            # get error message
            self._kkdll.Multi_GetEnumerateDevicesErrorMsg.restype = c_char_p
            retS = c_char_p(self._kkdll.Multi_GetEnumerateDevicesErrorMsg())
            kkres.data = retS.value.decode()
            if retI.value == -1:
                kkres.result_code = ErrorCode.KK_ERR_ENUM_SERIAL
            elif retI.value == -2:
                kkres.result_code = ErrorCode.KK_ERR_ENUM_USB
            else:
                kkres.result_code = ErrorCode.KK_ERR_ENUM_SERIAL_USB
        return kkres

    def get_host_and_IPs(self, l: [] =None) -> KK_Result:
        """Enumerates local IPv4 addresses and host name of local computer and
        delivers them in list l.
        If an error occurs KK_Result.data contains error message. Error could be
        on host name (no strings appended to l) or IP addresses (only host name
        is appended to l).
        For details see Multi_GetHostAndIPs in K+K library manual.
        @param l: list which host name and IP addresses are appended
        @return see KK_Result.result_code
        KK_NO_ERR: strings are appended to l: 
        first string: host, 
        next strings: one per IP address
        KK_ERR_BUFFER_TOO_SMALL: strings are appended to l, but truncated to 
        80 characters
        KK_ERR: operation fails, KK_Result.data contains error message
        """
        if l is None:
            l = []
        host = bytearray(80)
        ahost = ctypes.c_char * len(host)
        ips = bytearray(80)
        aips = ctypes.c_char * len(ips)
        error = bytearray(80)
        aerror = ctypes.c_char * len(error)
        retI = c_int32(self._kkdll.Multi_GetHostAndIPs(
                ahost.from_buffer(host), 
                aips.from_buffer(ips), 
                aerror.from_buffer(error)))
        kkres = KK_Result()
        if retI.value == 0:
            #error
            kkres.data = error.decode()
            kkres.result_code = ErrorCode.KK_ERR
        elif retI.value == 6:
            kkres.result_code = ErrorCode.KK_ERR_BUFFER_TOO_SMALL
        if host[0] != 0:
            l.append(self._bytearray2string(host))
            # ips only if host present
            if ips[0] != 0:
                # split string after comma
                s = self._bytearray2string(ips)
                while s is not None:
                    try:
                        i = s.index(',')
                        sub = s[:i]
                        l.append(sub)
                        s = s[i+1:]
                    except ValueError:
                        # ',' not found -> append last string
                        l.append(s)
                        s = None
        return kkres
            
    
    #-------------------------------------------------------------------------
    # Output path
    #-------------------------------------------------------------------------
    
    def get_output_path(self, source_id: int) -> KK_Result:
        """Get current output path for files generated by library 
        (test data, debug log) for source_id.
        For details see Multi_GetOutputPath in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @return: see KK_Result.result_code
        KK_NO_ERR: KK_Result.data contains current output path
        KK_PARAM_ERROR: invalid source_id, KK_Result.data contains 
        error message.
        """
        id_ = c_int32(source_id)
        self._kkdll.Multi_GetOutputPath.restype = c_char_p
        retS = c_char_p(self._kkdll.Multi_GetOutputPath(id_))
        kkres = KK_Result()
        kkres.data = retS.value.decode('ascii')
        if kkres.data.startswith(_ERR_SOURCE_NOT_FOUND):
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
        return kkres 
        
    def set_output_path(self, source_id: int, path: str) -> KK_Result:
        """Set actual library output path used for debug log or test data
        for source_id.
        For details see Multi_SetOutputPath in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @param path: new library output path
        @return: see KK_Result.result_code
        KK_NO_ERR: successful operation
        KK_PARAM_ERROR: invalid source_id, KK_Result.data contains 
        error message.
        KK_Err: call failed, KK_Result.data contains error message
        """
        id_ = c_int32(source_id)
        dllPath = path.encode('ascii')
        self._kkdll.Multi_SetOutputPath.restype = c_char_p
        retS = c_char_p(self._kkdll.Multi_SetOutputPath(id_, dllPath))
        kkres = KK_Result()
        if retS.value is not None:
            # error
            kkres.data = retS.value.decode('ascii')
            if kkres.data.startswith(_ERR_SOURCE_NOT_FOUND):
                kkres.result_code = ErrorCode.KK_PARAM_ERROR
            else:
                kkres.result_code = ErrorCode.KK_ERR
        return kkres 
    
    
    #-------------------------------------------------------------------------
    # Debug log
    #-------------------------------------------------------------------------
    
    def get_debug_filename(self, source_id: int) -> KK_Result:
        """Get current file name of debug log file for source_id
        For details see Multi_DebugGetFilename in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @return: see KK_Result.result_code
        KK_NO_ERR: KK_Result.data contains file name, maybe None,
        if no debug log file is opened
        KK_PARAM_ERROR: invalid source_id, KK_Result.data contains 
        error message.
        """
        id_ = c_int32(source_id)
        self._kkdll.Multi_DebugGetFilename.restype = c_char_p
        retS = c_char_p(self._kkdll.Multi_DebugGetFilename(id_))
        kkres = KK_Result()
        if retS.value is not None:
            # debug file name or error
            kkres.data = retS.value.decode('ascii')
            if kkres.data.startswith(_ERR_SOURCE_NOT_FOUND):
                kkres.result_code = ErrorCode.KK_PARAM_ERROR
        return kkres 
        
    def set_debug_log(self, source_id: int, dbg_on: bool, 
                      dbg_id: str) -> KK_Result:
        """Opens or closes debug log file of native K+K library for 
        source_id. Every call to a library function generates log outputs 
        to the debug file, if file is open.
        For details see Multi_Debug in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @param dbg_on: True opens, False closes debug log file
        @param dbg_id: source identifier of debug log file, part of file name 
        @return: see KK_Result.result_code
        KK_NO_ERR: successful operation
        KK_PARAM_ERROR: invalid source_id, KK_Result.data contains 
        error message.
        KK_Err: call failed, KK_Result.data contains error message
        """
        id_ = c_int32(source_id)
        ascii_id = None
        if dbg_id is not None:
            ascii_id = dbg_id.encode('ascii')
        self._kkdll.Multi_Debug.restype = c_char_p
        retS = c_char_p(self._kkdll.Multi_Debug(id_, dbg_on, ascii_id))
        kkres = KK_Result()
        if retS.value is not None:
            # error
            kkres.data = retS.value.decode('ascii')
            if kkres.data.startswith(_ERR_SOURCE_NOT_FOUND):
                kkres.result_code = ErrorCode.KK_PARAM_ERROR
            else:
                kkres.result_code = ErrorCode.KK_ERR
        return kkres 
    
    def set_debug_flags(self, source_id: int, report_log: bool, 
                        low_level_log: bool) -> KK_Result:
        """Sets extent of debug log file for source_id.
        For details see Multi_DebugFlags in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @param report_Log generate log output about received reports
        @param low_Level_Log generate log output about byte stream 
        received from/send to K+K device or K+K server.
        @return: see KK_Result.result_code
        KK_NO_ERR: successful operation
        KK_PARAM_ERROR: invalid source_id, KK_Result.data contains 
        error message.
        """
        id_ = c_int32(source_id)
        rep = ctypes.c_bool(report_log)
        low = ctypes.c_bool(low_level_log)
        retI = c_int32(self._kkdll.Multi_DebugFlags(id_, rep, low))
        kkres = KK_Result()
        if retI.value == 10:
            kkres.data = "Invalid parameter source_id: "+str(source_id)
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
        return kkres
        
    def set_debug_log_limit(self, source_id: int, log_type: DebugLogType, 
                            size: int) -> KK_Result:
        """Sets limits for debug log file for source_id.
        For details see Multi_DebugLogLimit in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @param log_type specifies debug file management, a value of 
        DebugLogType
        @param size maximum size of debug log file, used if 
        log_type != LOG_UNLIMITED
        @return: see KK_Result.result_code
        KK_NO_ERR: successful operation
        KK_PARAM_ERROR: invalid parameter value, KK_Result.data contains 
        error message.
        """
        # check parameter values
        kkres = KK_Result()
        if size < 0:
            kkres.data = "Invalid parameter size: "+str(size)  \
                            +", must be positive"
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
            return kkres
        id_ = c_int32(source_id)
        if log_type == DebugLogType.LOG_OVERWRITE:
            logt = c_byte(1)
        elif log_type == DebugLogType.LOG_CREATE_NEW:
            logt = c_byte(2)
        else:
            logt = c_byte(0)
        logs = c_uint(size)
        retI = c_int32(self._kkdll.Multi_DebugLogLimit(id_, logt, logs))
        if retI.value == 10:
            kkres.data = "Invalid parameter source_id: "+str(source_id)
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
        return kkres
    
    
    #-------------------------------------------------------------------------
    # Info requests
    #-------------------------------------------------------------------------
    
    def get_version(self) -> str:
        """Get version string from native K+K library.
        For details see Multi_DebugDLLVersion in K+K library manual.
        """
        self._kkdll.Multi_GetDLLVersion.restype = c_char_p
        version = c_char_p(self._kkdll.Multi_GetDLLVersion())
        return version.value.decode('ascii')

        
    def get_buffer_amount(self, source_id: int) -> int:
        """Get count of bytes in receive buffer for source_id.
        For details see Multi_GetBufferAmount in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @return: count of bytes in receive buffer not read yet
        """
        id_ = c_int32(source_id)
        retI = c_int32(self._kkdll.Multi_GetBufferAmount(id_))
        return retI.value
    
    def get_transmit_buffer_amount(self, source_id: int) -> int:
        """Get count of bytes in transmit buffer of K+K device
        connected with source_id.
        For details see Multi_GetTransmitBufferAmount in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @return: count of bytes in transmit buffer not sent yet
        """
        id_ = c_int32(source_id)
        retI = c_int32(self._kkdll.Multi_GetTransmitBufferAmount(id_))
        return retI.value
        
    def get_user_id(self, source_id: int) -> int:
        """Get user id assigned from K+K device connected with source_id.
        For details see Multi_GetUserID in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @return: 1..4: user id, -1: error
        """
        id_ = c_int32(source_id)
        retI = c_byte(self._kkdll.Multi_GetUserID(id_))
        return retI.value
    
    def is_file_device(self, source_id: int) -> bool:
        """Returns True, if data is read from file for source_id.
        For details see Multi_IsFileDevice in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @return True, if measurement data is read from file
        """
        id_ = c_int32(source_id)
        retI = c_bool(self._kkdll.Multi_IsFileDevice(id_))
        return retI.value
    
    def is_serial_device(self, source_id: int) -> bool:
        """Returns True, if data is read from serial connection for source_id.
        For details see Multi_IsSerialDevice in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @return True, if measurement data is read from serial connection
        """
        id_ = c_int32(source_id)
        retI = c_bool(self._kkdll.Multi_IsSerialDevice(id_))
        return retI.value
    
    def get_firmware_version(self, source_id: int) -> int:
        """Get firmware version number of K+K device
        connected with source_id.
        For details see Multi_GetFirmwareVersion in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @return: firmware version number
        """
        id_ = c_int32(source_id)
        retI = c_int32(self._kkdll.Multi_GetFirmwareVersion(id_))
        return retI.value

    def has_FRAM(self, source_id: int) -> bool:
        """Returns True, if K+K device connected with source_id is
        equipped with F-RAM memory.
        For details see Multi_HasFRAM in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @return True, if K+K device is equipped with F-RAM memory.
        """
        id_ = c_int32(source_id)
        retI = c_bool(self._kkdll.Multi_HasFRAM(id_))
        return retI.value
    
    def get_device_start_state(self, source_id: int) -> int:
        """Delivers the state of the K+K device at application start.
        For details see Multi_GetDeviceStartState in K+K library manual.
        @param source_id: source identifier returned by get_source_id
        @return
        0: Source-ID invalid or no time stamp received
        1: Cold start, K+K device was restarted
        2: Warm start
        """
        id_ = c_int32(source_id)
        retI = c_int32(self._kkdll.Multi_GetDeviceStartState(id_))
        return retI.value
        
    #-------------------------------------------------------------------------
    # Calibration
    #-------------------------------------------------------------------------

    def set_NSZ_calibration_data(self, source_id: int, 
                                 calib_data: []) -> KK_Result:
        """Writes NSZ calibration data to K+K device connected with source_id.
        Needs firmware version 62 or higher, not supported for serial connections.
        For details see Multi_SetNSZCalibrationData in K+K library manual.
        @param source_id: source identifier returned by get_source_id
        @param calib_data: list of float with calibration value per channel
        in nanoseconds  
        @return: see KK_Result.result_code
        KK_NO_ERR: successful operation
        KK_Err: command failed, KK_Result.data contains error message
        KK_PARAM_ERROR: invalid parameter value, KK_Result.data contains 
        error message.
        KK_ERR_NOT_SUPPORTED: writing NSZ calibration data not supported
        by K+K device, KK_Result.data contains error message.
        """
        # check parameter values
        kkres = KK_Result()
        if (calib_data == None) or (calib_data == []):
            kkres.data = "Parameter calib_data missing"
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
        elif len(calib_data) > KK_MAX_CHANNELS:
            kkres.data = "Invalid parameter calib_data: too many channels"
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
        if kkres.result_code != ErrorCode.KK_NO_ERR:
            return kkres
            
        id_ = c_int32(source_id)
        # generate floating point string, separated by semicolon
        # with 3 digits behind decimal separator
        # use locale, set in set_decimal_separator
        s_ = ''
        for f in calib_data:
            s_ = s_ + locale.format('%.3f', f) + ';'
        # delete last ;
        s_ = s_[:-1]
        data_ = s_.encode('ascii')
        retI = c_int32(self._kkdll.Multi_SetNSZCalibrationData(id_, data_))
        if retI.value == 0:
            # check serial connection
            if self.is_serial_device(self, source_id):
                kkres.data = "Serial connection not supported"
            else:
                kkres.data = "Conversion error, set decimal separator!"
            kkres.result_code = ErrorCode.KK_ERR
        elif retI.value == 10:
            kkres.data = "Invalid parameter source_id: "+str(source_id)
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
        elif retI.value == 12:
            kkres.data = "Feature not supported, needs firmware version 62 or higher"
            kkres.result_code = ErrorCode.KK_ERR_NOT_SUPPORTED
        return kkres


    #-------------------------------------------------------------------------
    # FHR settings
    #-------------------------------------------------------------------------

    def get_FHR_settings(self, source_id: int) -> KK_Result:
        """Requests FHR settings from K+K device connected with source_id.
        K+K device responds with 0x7902-Report including requested data.
        Needs firmware version 67 or higher
        For details see Multi_ReadFHRData in K+K library manual.
        @param source_id: source identifier returned by get_source_id
        @return: see KK_Result.result_code
        KK_NO_ERR: successful operation
        KK_Err: command failed, KK_Result.data contains error message
        KK_PARAM_ERROR: invalid parameter value, KK_Result.data contains 
        error message.
        KK_ERR_NOT_SUPPORTED: requesting FHR settings not supported
        by K+K device, KK_Result.data contains error message.
        """
        id_ = c_int32(source_id)
        kkres = KK_Result()
        retI = c_int32(self._kkdll.Multi_ReadFHRData(id_))
        if retI.value == 0:
            kkres.data = "Command failed"
            kkres.result_code = ErrorCode.KK_ERR
        elif retI.value == 10:
            kkres.data = "Invalid parameter source_id: "+str(source_id)
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
        elif retI.value == 12:
            kkres.data = "Feature not supported, needs firmware version 67 or higher"
            kkres.result_code = ErrorCode.KK_ERR_NOT_SUPPORTED
        return kkres

    def set_FHR_settings(self, source_id: int,
                         fhr_data: str) -> KK_Result:
        """Writes FHR settings to K+K device connected with source_id.
        Needs firmware version 67 or higher, not supported for serial connections.
        For details see Multi_SetFHRData in K+K library manual.
        @param source_id: source identifier returned by get_source_id
        @param fhr_data: string representation of FHRSettings
        @return: see KK_Result.result_code
        KK_NO_ERR: successful operation
        KK_Err: command failed, KK_Result.data contains error message
        KK_PARAM_ERROR: invalid parameter value, KK_Result.data contains 
        error message.
        KK_ERR_NOT_SUPPORTED: writing NSZ calibration data not supported
        by K+K device, KK_Result.data contains error message.
        """
        # check parameter values
        kkres = KK_Result()
        try:
            FHRSettings(fhr_data)
        except:
            kkres.data = "Invalid parameter fhr_data"
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
            return kkres
            
        id_ = c_int32(source_id)
        data_ = fhr_data.encode('ascii')
        retI = c_int32(self._kkdll.Multi_SetFHRData(id_, data_))
        if retI.value == 0:
            # check serial connection
            if self.is_serial_device(self, source_id):
                kkres.data = "Serial connection not supported"
            else:
                kkres.data = "Conversion error, set decimal separator!"
            kkres.result_code = ErrorCode.KK_ERR
        elif retI.value == 10:
            kkres.data = "Invalid parameter source_id: "+str(source_id)
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
        elif retI.value == 12:
            kkres.data = "Feature not supported, needs firmware version 67 or higher"
            kkres.result_code = ErrorCode.KK_ERR_NOT_SUPPORTED
        return kkres
    
    
    #-------------------------------------------------------------------------
    # Open / Close connection
    #-------------------------------------------------------------------------
    
    def open_connection(self, source_id: int, connection: str, 
                        blocking_IO: bool) -> KK_Result:
        """Opens connection for source_id to K+K device or K+K server
        or read data from file according to connection.
        A previously opened connection for source_id will be closed.
        For details see Multi_OpenConnection in K+K library manual.
        @param source_id: source identifier returned by get_source_id
        @param connection: String describes connection to open
        @param param blocking_IO: open connection with blocking read and 
        write operations
        @return: see KK_Result.result_code
        KK_NO_ERR: successful operation
        KK_PARAM_ERROR: invalid parameter value, KK_Result.data contains 
        error message.
        KK_ERR: open failed, KK_Result.data contains error message.
        """
        id_ = c_int32(source_id)
        conn = connection.encode('ascii')
        b_IO =  ctypes.c_bool(blocking_IO)
        # conn needs 1024 byte buffer
        for i in range(len(conn)):
            self._buffer[i] = conn[i]
        # append terminating 0
        self._buffer[len(conn)] = 0
        # mutable variable needed
        char_array = ctypes.c_char * len(self._buffer)
        kkres = KK_Result()
        retI = c_int32(self._kkdll.Multi_OpenConnection(
                id_, char_array.from_buffer(self._buffer), b_IO))
        if retI.value != 1:
            # buffer contains error message
            kkres.data = self._bytearray2string(self._buffer)
            if retI.value == 10:
                kkres.result_code = ErrorCode.KK_PARAM_ERROR
            else:
                kkres.result_code = ErrorCode.KK_ERR
        
        return kkres
        
    def close_connection(self, source_id: int):
        """Closes a previously opened connection for source_id.
        For details see Multi_CloseConnection in K+K library manual.
        @param source_id: source identifier returned by get_source_id
        """
        id_ = c_int32(source_id)
        self._kkdll.Multi_CloseConnection(id_)
        
    
    #-------------------------------------------------------------------------
    # Get report
    #-------------------------------------------------------------------------
    
    def set_decimal_separator(self, source_id: int, 
                              separator: str) -> KK_Result:
        """Sets decimal separator used to convert floating point numbers
        into string.
        For details see Multi_SetDecimalSeparator in K+K library manual.
        @param source_id: source identifier returned by get_source_id
        @param separator: must be '.' or ',' 
        @return: see KK_Result.result_code
        KK_NO_ERR: successful operation
        KK_PARAM_ERROR: invalid parameter value, KK_Result.data contains 
        error message.
        """
        # check parameter values
        kkres = KK_Result()
        if (separator != '.') and (separator != ','):
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
            kkres.data = "Invalid parameter separator: "+separator
            return kkres
        # set locale for conversion string <-> float
        if separator == '.':
            locale.setlocale(locale.LC_NUMERIC, 'en_US.utf8')
        else:
            locale.setlocale(locale.LC_NUMERIC, 'de_DE.utf8')
        id_ = c_int32(source_id)
        b = bytes(separator, 'ascii')
        sep = c_char(b[0])
        retI = c_int32(self._kkdll.Multi_SetDecimalSeparator(id_, sep))
        if retI.value == 10:
                kkres.result_code = ErrorCode.KK_PARAM_ERROR
                kkres.data = "Invalid parameter source_id: "+str(source_id)
        return kkres        
    
    def set_NSZ(self, source_id: int, aNSZ: int) -> KK_Result:
        """Sets count of NSZ measurements sent by K+K measurement card.
        For details see Multi_SetNSZ in K+K library manual.
        @param source_id: source identifier returned by get_source_id
        @param aNSZ: must be 1 or 2 
        @return: see KK_Result.result_code
        KK_NO_ERR: successful operation
        KK_PARAM_ERROR: invalid parameter value, KK_Result.data contains 
        error message.
        """
        # check parameter values
        kkres = KK_Result()
        if (aNSZ != 1) and (aNSZ != 2):
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
            kkres.data = "Invalid parameter aNSZ: "+str(aNSZ)
            return kkres
        id_ = c_int32(source_id)
        nsz = c_int32(aNSZ)
        retI = c_int32(self._kkdll.Multi_SetNSZ(id_, nsz))
        if retI.value == 10:
                kkres.result_code = ErrorCode.KK_PARAM_ERROR
                kkres.data = "Invalid parameter source_id: "+str(source_id)
        return kkres
    
    def get_report(self, source_id: int) -> KK_Result:
        """Gets next report for source_id received via current connection from
        K+K device or K+K server or read from file and write it to KK_Result.data.
        For details see Multi_GetReport in K+K library manual.
        @param source_id: source identifier returned by get_source_id
        @return: see KK_Result.result_code
        KK_NO_ERR: operation successful, KK_Result.data contains report or
        None, if no report available
        KK_ERR_BUFFER_TOO_SMALL: operation successful, but string in 
        KK_Result.data is truncated to 1024 characters.
        all other codes are error numbers and KK_Result.data contains 
        error message:
        KK_PARAM_ERROR: invalid source_id
        KK_ERR_WRITE: Writing to device/server failed. Connection is closed.
        For details see Multi_SendCommand in K+K library manual. 
        KK_ERR_SERVER_DOWN: K+K TCP server is not online. Connection is closed.
        KK_ERR_DEVICE_NOT_CONNECTED: No connection to K+K device (connection has
        not been established or usb cable is unplugged) 
        KK_ERR_BUFFER_OVERFLOW: Data was lost. App does not read fast enough.
        KK_HARDWARE_FAULT: Fault in measurement hardware. Connection to
        K+K device is closed.
        KK_ERR_RECONNECTED: A previously interrupted connection is reconnectd now
        with data loss.
        """
        id_ = c_int32(source_id)
        # mutable 1024 bytes buffer needed
        char_array = ctypes.c_char * len(self._buffer)
        # get log report
        retI = c_int32(self._kkdll.Multi_GetReport(id_, 
                        char_array.from_buffer(self._buffer)))
        kkres = KK_Result()
        # convert to string
        kkres.data = self._bytearray2string(self._buffer)
        if retI.value == 6:
            kkres.result_code = ErrorCode.KK_ERR_BUFFER_TOO_SMALL
        elif retI.value == 0:
            kkres.result_code = ErrorCode.KK_ERR
        elif retI.value == 3:
            kkres.result_code = ErrorCode.KK_ERR_WRITE
        elif retI.value == 4:
            kkres.result_code = ErrorCode.KK_ERR_SERVER_DOWN
        elif retI.value == 7:
            kkres.result_code = ErrorCode.KK_ERR_DEVICE_NOT_CONNECTED
        elif retI.value == 8:
            kkres.result_code = ErrorCode.KK_ERR_BUFFER_OVERFLOW
        elif retI.value == 9:
            kkres.result_code = ErrorCode.KK_HARDWARE_FAULT
        elif retI.value == 10:
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
        elif retI.value == 13:
            kkres.result_code = ErrorCode.KK_ERR_RECONNECTED
        return kkres
    
    def set_send_7016(self, source_id: int, value: bool) -> KK_Result:
        """The 100ms timestamps received from the K+K device are passed
        on to the application by default with Report 7000.
        Here it is now possible to switch to Report 7016.
        For details see Multi_SetSend7016 in K+K library manual.
        @param source_id: source identifier returned by get_source_id
        @param value:
        True: send Report 7016
        False: send Report 7000 (Default)
        @return: see KK_Result.result_code
        KK_NO_ERR: operation successful
        KK_PARAM_ERROR: invalid source_id
        """
        id_ = c_int32(source_id)
        val = c_bool(value)
        kkres = KK_Result()
        retI = c_int32(self._kkdll.Multi_SetSend7016(id_, val))        
        if retI.value == 10:
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
        return kkres

        
    #-------------------------------------------------------------------------
    # Send command
    #-------------------------------------------------------------------------
    
    def get_pending_commands_count(self, source_id: int) -> int:
        """Gets count of buffered (not yet sent) commands for source_id.
        For details see Multi_GetPendingCmdsCount in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @return: count of waiting commands
        """
        id_ = c_int32(source_id)
        retI = c_byte(self._kkdll.Multi_GetPendingCmdsCount(id_))
        return retI.value
    
    def set_command_limit(self, source_id: int, limit: int) -> KK_Result:
        """Sets limit of command waiting queue for source_id to limit.
        For an unlimited waiting queue set limit to 0.
        For details see Multi_SetCommadLimit in K+K library manual.
        @param source_id: source identifier returned by get_source_id
        @param limit: length of waiting queue(>=0), 0=unlimited, 
        default=unlimited 
        @return: see KK_Result.result_code
        KK_NO_ERR: successful operation
        KK_PARAM_ERROR: invalid parameter value, KK_Result.data contains 
        error message.
        """
        # check parameter values
        kkres = KK_Result()
        if limit < 0:
            kkres.data = "Invalid parameter limit: "+str(limit)
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
            return kkres
        id_ = c_int32(source_id)
        lim = c_int32(limit)
        retI = c_int32(self._kkdll.Multi_SetCommandLimit(id_, lim))    
        if retI.value == 10:
                kkres.result_code = ErrorCode.KK_PARAM_ERROR
                kkres.data = "Invalid parameter source_id: "+str(source_id)
        return kkres
        
    def remote_login(self, source_id: int, password: int) -> KK_Result:
        """Remote login procedure on K+K device connected to source_id.
        For details see Multi_RemoteLogin in K+K library manual.
        @param source_id: source identifier returned by get_source_id
        @param password: remote password
        @return: see KK_Result.result_code
        KK_NO_ERR: successful operation
        all other codes are error numbers and KK_Result.data contains 
        error message:
        KK_PARAM_ERROR: invalid parameter value
        KK_ERR: invalid password
        KK_CMD_IGNORED: command rejected
        """
        id_ = c_int32(source_id)
        password_ = c_ulong(password)
        # mutable 1024 bytes buffer needed
        char_array = ctypes.c_char * len(self._buffer)
        # get log report
        retI = c_int32(self._kkdll.Multi_RemoteLogin(id_, password_, 
                        char_array.from_buffer(self._buffer)))
        kkres = KK_Result()
        if retI.value != 1:
            # buffer contains error message
            kkres.data = self._bytearray2string(self._buffer)
            if retI.value == 10:
                kkres.result_code = ErrorCode.KK_PARAM_ERROR
            elif retI.value == 0:
                kkres.result_code = ErrorCode.KK_ERR
            elif retI.value == 11:
                kkres.result_code = ErrorCode.KK_CMD_IGNORED
        return kkres
    
    def send_command(self, source_id: int, command: bytes) -> KK_Result:
        """Adds command to waiting queue of source_id.
        If there is no current connection or waiting queue is full,
        command is rejected (KK_CMD_IGNORED). 
        For details see Multi_SendCommand in K+K library manual.
        @param source_id: source identifier returned by get_source_id
        @param command: command bytes to be sent
        @return: see KK_Result.result_code
        KK_NO_ERR: successful operation
        all other codes are error numbers and KK_Result.data contains 
        error message:
        KK_PARAM_ERROR: invalid parameter value
        KK_ERR: an error occurred
        KK_CMD_IGNORED: command rejected
        """
        # check parameter values
        kkres = KK_Result()
        if len(command) == 0:
            kkres.data = "Invalid parameter command: "+command
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
            return kkres
        id_ = c_int32(source_id)
        l = c_int32(len(command))
        # command needs 1024 byte buffer
        for i in range(len(command)):
            self._buffer[i] = command[i]
        # mutable variable needed
        char_array = ctypes.c_char * len(self._buffer)
        retI = c_int32(self._kkdll.Multi_SendCommand(
                id_, char_array.from_buffer(self._buffer), l))
        if retI.value != 1:
            # buffer contains error message
            kkres.data = self._bytearray2string(self._buffer)
            if retI.value == 10:
                kkres.result_code = ErrorCode.KK_PARAM_ERROR
            elif retI.value == 0:
                kkres.result_code = ErrorCode.KK_ERR
            elif retI.value == 11:
                kkres.result_code = ErrorCode.KK_CMD_IGNORED
        return kkres
    
    
    #-------------------------------------------------------------------------
    # Local TCP server
    #-------------------------------------------------------------------------
    
    def start_TCP_server(self, source_id: int, aPort: int) -> KK_Result:
        """Starts local TCP server for source_id on port aPort.
        If aPort == 0, port number is assigned by system and returned 
        in KK_Result.intValue
        For details see Multi_StartTcpServer in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @param aPort port number for TCP server, system assigned value
        see KK_Result.intValue
        @return: see KK_Result.result_code
        KK_NO_ERR: successful operation
        KK_PARAM_ERROR: invalid parameter value, KK_Result.data contains 
        error message.
        KK_ERR: operation failed, KK_Result.data contains error message.
        """
        id_ = c_int32(source_id)
        port_ = c_int32(aPort)
        kkres = KK_Result()
        retI = c_int32(self._kkdll.Multi_StartTcpServer(id_, byref(port_)))
        if retI.value == 10:
                kkres.result_code = ErrorCode.KK_PARAM_ERROR
                kkres.data = "Invalid parameter source_id: "+str(source_id)
        elif retI.value == 0:
                kkres.result_code = ErrorCode.KK_ERR
                self._kkdll.Multi_GetTcpServerError.restype = c_char_p
                error = c_char_p(self._kkdll.Multi_GetTcpServerError(id_))
                kkres.data = error.value.decode('ascii')
        else:
            kkres.int_value = port_.value
        return kkres
    
    def stop_TCP_server(self, source_id: int) -> KK_Result:
        """Stops local TCP server for source_id.
        All client connections are disconnected.
        For details see Multi_StopTcpServer in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @return: see KK_Result.result_code
        KK_NO_ERR: successful operation
        KK_PARAM_ERROR: invalid parameter value, KK_Result.data contains 
        error message.
        KK_ERR: operation failed, KK_Result.data contains error message.
        """
        id_ = c_int32(source_id)
        kkres = KK_Result()
        retI = c_int32(self._kkdll.Multi_StopTcpServer(id_))
        if retI.value == 10:
                kkres.result_code = ErrorCode.KK_PARAM_ERROR
                kkres.data = "Invalid parameter source_id: "+str(source_id)
        elif retI.value == 0:
                kkres.result_code = ErrorCode.KK_ERR
                self._kkdll.Multi_GetTcpServerError.restype = c_char_p
                error = c_char_p(self._kkdll.Multi_GetTcpServerError(id_))
                kkres.data = error.value.decode('ascii')
        return kkres
    
    def report_TCP_log(self, source_id: int, data: str, logType: str) -> KK_Result:
        """Transmits log entry data for LOG level type logType to local 
        TCP server on source_id.
        Local TCP server proceeds data to connected TCP receiver clients.
        If an error occurs (source_id invalid, source without local tcp server), 
        call is ignored.
        For details see Multi_TcpReportLog in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @param data Log entry to transmit to connected clients
        @param logType specifies log entry type, one of following values: 
            'PHASELOG', 'FREQLOG', 'PHASEDIFFLOG', 'NSZLOG', 'NSZDIFFLOG',
            'PHASEPREDECESSORLOG', 'USERLOG1', 'USERLOG2'
        @return: see KK_Result.result_code
        KK_NO_ERR: successful or ignored operation
        KK_PARAM_ERROR: invalid parameter value, KK_Result.data contains 
        error message.
        """
        # check parameter values
        kkres = KK_Result()
        if data == None:
            kkres.data = "Missing parameter data"
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
        data_ = data.encode('ascii')
        if logType == 'PHASELOG':
            log_ = c_int32(0)
        elif logType == 'FREQLOG':
            log_ = c_int32(1)
        elif logType == 'PHASEDIFFLOG':
            log_ = c_int32(2)
        elif logType == 'NSZLOG':
            log_ = c_int32(3)
        elif logType == 'NSZEDIFFLOG':
            log_ = c_int32(4)
        elif logType == 'PHASEPREDECESSORLOG':
            log_ = c_int32(5)
        elif logType == 'USERLOG1':
            log_ = c_int32(6)
        elif logType == 'USERLOG2':
            log_ = c_int32(7)
        else:
            kkres.data = "Invalid parameter logType: "+logType
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
            return kkres
        id_ = c_int32(source_id)
        self._kkdll.Multi_TcpReportLog(id_, data_, log_)
        return kkres
    
    
    #-------------------------------------------------------------------------
    # Connect to TCP server on LOG level
    #-------------------------------------------------------------------------
    
    def open_TCP_log(self, source_id: int, ip_port: str, 
                     mode: str) -> KK_Result:
        """Opens connection for source_id to K+K TCP server on address
        ip_Port for log level entries.
        For details see Multi_OpenTcpLog in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @param ip_Port IPaddress:port with
        IPaddress: IPv4 address of K+K TCP server, e.g. 192.168.178.98 or 
                    127.0.0.1 for local host
        port: port number (16 bit value) of TCP server.
        @param mode report mode to receive, one of following values: 
            'PHASELOG', 'FREQLOG', 'PHASEDIFFLOG', 'NSZLOG', 'NSZDIFFLOG',
            'PHASEPREDECESSORLOG', 'USERLOG1', 'USERLOG2'
        @return: see KK_Result.result_code
        KK_NO_ERR: successful operation
        KK_PARAM_ERROR: invalid parameter value, KK_Result.data contains 
        error message.
        KK_ERR: open failed, KK_Result.data contains error message.
        """
        # check parameter values
        kkres = KK_Result()
        if ((mode != 'PHASELOG') and (mode != 'FREQLOG') 
            and (mode != 'PHASEDIFFLOG')
            and (mode != 'NSZLOG') and (mode != 'NSZDIFFLOG')
            and (mode != 'PHASEPREDECESSORLOG')
            and (mode != 'USERLOG!') and (mode != 'USERLOG2')
            ):
            kkres.data = "Invalid parameter mode: "+mode
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
            return kkres
        if ip_port is None:
            kkres.data = "Parameter missing: ip_port"
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
            return kkres
        id_ = c_int32(source_id)
        ip = ip_port.encode('ascii')
        m = c_char_p(mode.encode('ascii'))
        # ip needs 1024 byte buffer
        for i in range(len(ip)):
            self._buffer[i] = ip[i]
        # append terminating 0
        self._buffer[len(ip)] = 0
        # mutable variable needed
        char_array = ctypes.c_char * len(self._buffer)
        retI = c_int32(self._kkdll.Multi_OpenTcpLog(
                id_, char_array.from_buffer(self._buffer), m))
        if retI.value != 1:
            # buffer contains error message
            kkres.data = self._bytearray2string(self._buffer)
            if kkres.data.startswith(_ERR_SOURCE_NOT_FOUND):
                kkres.result_code = ErrorCode.KK_PARAM_ERROR
            else:
                kkres.result_code = ErrorCode.KK_ERR
        return kkres
        
    def open_TCP_log_time(self, source_id: int, ip_port: str, 
                     mode: str, format_str: str) -> KK_Result:
        """Opens connection for source_id to K+K TCP server on address
        ip_Port for log level entries.
        For details see Multi_OpenTcpLogTime in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @param ip_Port IPaddress:port with
        IPaddress: IPv4 address of K+K TCP server, e.g. 192.168.178.98 or 
                    127.0.0.1 for local host
        port: port number (16 bit value) of TCP server.
        @param mode report mode to receive, one of following values: 
            'PHASELOG', 'FREQLOG', 'PHASEDIFFLOG', 'NSZLOG', 'NSZDIFFLOG',
            'PHASEPREDECESSORLOG', 'USERLOG1', 'USERLOG2'
        @param format: string to format UTC time stamp
            e.g. 'YYYYMMDD HH:NN:SS.ZZZ'
        @return: see KK_Result.result_code
        KK_NO_ERR: successful operation
        KK_PARAM_ERROR: invalid parameter value, KK_Result.data contains 
        error message.
        KK_ERR: open failed, KK_Result.data contains error message.
        """
        # check parameter values
        kkres = KK_Result()
        if ((mode != 'PHASELOG') and (mode != 'FREQLOG') 
            and (mode != 'PHASEDIFFLOG')
            and (mode != 'NSZLOG') and (mode != 'NSZDIFFLOG')
            and (mode != 'PHASEPREDECESSORLOG')
            and (mode != 'USERLOG!') and (mode != 'USERLOG2')
            ):
            kkres.data = "Invalid parameter mode: "+mode
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
            return kkres
        if ip_port is None:
            kkres.data = "Parameter missing: ip_port"
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
            return kkres
        if format_str is None:
            kkres.data = "Parameter missing: format_str"
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
            return kkres
            
        id_ = c_int32(source_id)
        ip = ip_port.encode('ascii')
        m = c_char_p(mode.encode('ascii'))
        f = c_char_p(format_str.encode('ascii'))
        # ip needs 1024 byte buffer
        for i in range(len(ip)):
            self._buffer[i] = ip[i]
        # append terminating 0
        self._buffer[len(ip)] = 0
        # mutable variable needed
        char_array = ctypes.c_char * len(self._buffer)
        retI = c_int32(self._kkdll.Multi_OpenTcpLogTime(
                id_, char_array.from_buffer(self._buffer), m, f))
        if retI.value != 1:
            # buffer contains error message
            kkres.data = self._bytearray2string(self._buffer)
            if kkres.data.startswith(_ERR_SOURCE_NOT_FOUND):
                kkres.result_code = ErrorCode.KK_PARAM_ERROR
            else:
                kkres.result_code = ErrorCode.KK_ERR
        return kkres
        
    def open_TCP_log_type(self, source_id: int, ip_port: str, 
                     log_type: int, format_str: str) -> KK_Result:
        """Opens connection for source_id to K+K TCP server on address
        ip_Port for log level entries.
        For details see Multi_OpenTcpLogType in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @param ip_Port IPaddress:port with
        IPaddress: IPv4 address of K+K TCP server, e.g. 192.168.178.98 or 
                    127.0.0.1 for local host
        port: port number (16 bit value) of TCP server.
        @param log_type report mode to receive 0..7 
        @param format: string to format UTC time stamp or none
            e.g. 'YYYYMMDD HH:NN:SS.ZZZ'
        @return: see KK_Result.result_code
        KK_NO_ERR: successful operation
        KK_PARAM_ERROR: invalid parameter value, KK_Result.data contains 
        error message.
        KK_ERR: open failed, KK_Result.data contains error message.
        """
        # check parameter values
        kkres = KK_Result()
        if ((log_type < 0) or (log_type > 7)): 
            kkres.data = "Invalid parameter log_type: "+log_type
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
            return kkres
        if ip_port is None:
            kkres.data = "Parameter missing: ip_port"
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
            return kkres
            
        id_ = c_int32(source_id)
        ip = ip_port.encode('ascii')
        l_ = c_int32(log_type)
        
        f = None
        if format_str is not None:
            f = c_char_p(format_str.encode('ascii'))
        # ip needs 1024 byte buffer
        for i in range(len(ip)):
            self._buffer[i] = ip[i]
        # append terminating 0
        self._buffer[len(ip)] = 0
        # mutable variable needed
        char_array = ctypes.c_char * len(self._buffer)
        retI = c_int32(self._kkdll.Multi_OpenTcpLogType(
                id_, char_array.from_buffer(self._buffer), l_, f))
        if retI.value != 1:
            # buffer contains error message
            kkres.data = self._bytearray2string(self._buffer)
            if kkres.data.startswith(_ERR_SOURCE_NOT_FOUND):
                kkres.result_code = ErrorCode.KK_PARAM_ERROR
            else:
                kkres.result_code = ErrorCode.KK_ERR
        return kkres
        
    def close_TCP_log(self, source_id: int):        
        """Closes previously opened connection for source_id to 
        LOG level K+K TCP server.
        For details see Multi_CloseTcpLog in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        """
        id_ = c_int32(source_id)
        self._kkdll.Multi_CloseTcpLog(id_)
        
    def get_TCP_log(self, source_id: int) -> KK_Result:
        """Get next log level entry for source_id received from 
        K+K TCP server and write it to KK_Result.data.
        KK_Result.data = None, if no reports available.
        For details see Multi_GetTcpLog in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @return see KK_Result.resultCode
        KK_NO_ERR: operation successful, KK_Result.data contains report or
        None, if no report available
        KK_ERR_BUFFER_TOO_SMALL: operation successful, but string in 
        KK_Result.data is truncated to 1024 characters.
        all other codes are error numbers and KK_Result.data contains 
        error message:
        KK_PARAM_ERROR: invalid source_id
        KK_ERR_SERVER_DOWN: K+K TCP server is not online. Connection is closed.
        KK_ERR_BUFFER_OVERFLOW: Data was lost. App does not read fast enough.
        """
        id_ = c_int32(source_id)
        # mutable 1024 bytes buffer needed
        char_array = ctypes.c_char * len(self._buffer)
        # get log report
        retI = c_int32(self._kkdll.Multi_GetTcpLog(id_, 
                        char_array.from_buffer(self._buffer)))
        kkres = KK_Result()
        # convert to string
        kkres.data = self._bytearray2string(self._buffer)
        if retI.value == 6:
            kkres.result_code = ErrorCode.KK_ERR_BUFFER_TOO_SMALL
        elif retI.value == 10:
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
        elif retI.value == 4:
            kkres.result_code = ErrorCode.KK_ERR_SERVER_DOWN
        elif retI.value == 8:
            kkres.result_code = ErrorCode.KK_ERR_BUFFER_OVERFLOW
        return kkres
    
    def send_TCP_data(self, source_id: int, data: str) -> KK_Result:
        """Sends the string contained in data to the TCP server connected for 
        source_id at library level or log level and delivers response. 
        For details see Multi_TcpAppData in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @param data: string to send 
        @return see KK_Result.resultCode
        KK_NO_ERR: operation successful, response in KK_Result.data
        all other codes are error numbers and KK_Result.data contains 
        error message:
        KK_PARAM_ERROR: invalid source_id
        KK_ERR_SERVER_DOWN: no connection to K+K TCP server
        KK_ERR: error reported by K+K TCP server
        """
        id_ = c_int32(source_id)
        data_ = data.encode('ascii')
        # data needs 1024 byte buffer
        for i in range(len(data_)):
            self._buffer[i] = data_[i]
        # append terminating 0
        self._buffer[len(data_)] = 0
        # mutable variable needed
        char_array = ctypes.c_char * len(self._buffer)
        retI = c_int32(self._kkdll.Multi_TcpAppData(
                id_, char_array.from_buffer(self._buffer)))
        kkres = KK_Result()
        # convert to string
        kkres.data = self._bytearray2string(self._buffer)
        if retI.value == 10:
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
        elif retI.value == 4:
            kkres.result_code = ErrorCode.KK_ERR_SERVER_DOWN
        elif retI.value != 1:
            kkres.result_code = ErrorCode.KK_ERR
        return kkres
    
    
    #-------------------------------------------------------------------------
    # Test data
    #-------------------------------------------------------------------------
    
    def start_save_binary_data(self, source_id: int, dbg_id: str) -> KK_Result:
        """Start generating test data for source_id in binary file.
        For details see Multi_StartSaveBinaryData in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @param dbg_id: source identifier of binary file, part of file name 
        @return see KK_Result.resultCode
        KK_NO_ERR: operation successful
        KK_PARAM_ERROR: invalid source_id, no connection for source_id,
            KK_Result.data contains error message
        """
        id_ = c_int32(source_id)
        ascii_id = None
        if dbg_id is not None:
            ascii_id = dbg_id.encode('ascii')
        retI = c_int32(self._kkdll.Multi_StartSaveBinaryData(id_, ascii_id)) 
        kkres = KK_Result()
        if retI.value == 10:
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
            kkres.data = "Invalid parameter source_id: "+str(source_id)
        elif retI.value == 7:
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
            kkres.data = "No connection for source_id: "+str(source_id)
        return kkres
    
    def stop_save_binary_data(self, source_id: int) -> KK_Result:
        """Stops generating binary test data for source_id, closes
        binary file.
        Binary file is closed too, when current connection is closed.
        For details see Multi_StopSaveBinaryData in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @return see KK_Result.resultCode
        KK_NO_ERR: operation successful
        KK_PARAM_ERROR: invalid source_id, no connection for source_id,
            KK_Result.data contains error message
        """
        id_ = c_int32(source_id)
        retI = c_int32(self._kkdll.Multi_StopSaveBinaryData(id_)) 
        kkres = KK_Result()
        if retI.value == 10:
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
            kkres.data = "Invalid parameter source_id: "+str(source_id)
        elif retI.value == 7:
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
            kkres.data = "No connection for source_id: "+str(source_id)
        return kkres
    
    def start_save_report_data(self, source_id: int, dbg_id: str) -> KK_Result:
        """Start generating test data for source_id in text file.
        For details see Multi_StartSaveReportData in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @param dbg_id: source identifier of binary file, part of file name 
        @return see KK_Result.resultCode
        KK_NO_ERR: operation successful
        KK_PARAM_ERROR: invalid source_id, KK_Result.data contains error message
        """
        id_ = c_int32(source_id)
        ascii_id = None
        if dbg_id is not None:
            ascii_id = dbg_id.encode('ascii')
        retI = c_int32(self._kkdll.Multi_StartSaveReportData(id_, ascii_id)) 
        kkres = KK_Result()
        if retI.value == 10:
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
            kkres.data = "Invalid parameter source_id: "+str(source_id)
        return kkres
    
    def stop_save_report_data(self, source_id: int) -> KK_Result:
        """Stops generating report test data for source_id, closes
        text file.
        For details see Multi_StopSaveReportData in K+K library manual.
        @param source_id: source identifier returned by get_source_id 
        @return see KK_Result.resultCode
        KK_NO_ERR: operation successful
        KK_PARAM_ERROR: invalid source_id, KK_Result.data contains error message
        """
        id_ = c_int32(source_id)
        retI = c_int32(self._kkdll.Multi_StopSaveReportData(id_)) 
        kkres = KK_Result()
        if retI.value == 10:
            kkres.result_code = ErrorCode.KK_PARAM_ERROR
            kkres.data = "Invalid parameter source_id: "+str(source_id)
        return kkres
    
    